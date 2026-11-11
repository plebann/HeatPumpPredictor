# Ewaluacja trafności prognozy energii względem faktycznego zużycia pompy ciepła

- Date: 2026-11-07
- Category: feature
- Priority signal: medium — brak wiedzy, jak dokładny jest algorytm; sensory Scheduled Forecast powstały tylko po to, żeby to wizualizować
- Risk signal: medium — rozszerza istniejący `forecast_validation` (walidacja temperatur) i dotyka handlera publicznego serwisu; kontrakt serwisu musi pozostać bez zmian
- Routing: Next: om-auto-write-spec "Evaluate energy forecast accuracy against actual heat pump consumption — brief: .ai/specs/briefs/2026-11-07-forecast-energy-accuracy.md"

## Problem

Serwis `heat_pump_predictor.calculate_forecast_energy` jest wołany z zewnątrz (automatyzacje HA) i zwraca prognozę zużycia energii dla okna godzin. Nie ma sposobu, żeby sprawdzić, jak dokładne były te prognozy względem późniejszego, faktycznego zużycia pompy ciepła. Dotychczas służyły do tego sensory `Scheduled Forecast`, utworzone wyłącznie do wizualizacji dokładności. Potrzebna jest ciągle aktualizowana statystyka dokładności (accuracy), uwzględniająca poprzednie wyniki.

## Agreed direction

Rozszerzyć istniejący `ForecastValidationManager` (`forecast_validation.py`: `Store`, `async_validate_due`, prune, odczyt Recordera, ponawianie) o walidację energii, wykorzystując jego infrastrukturę, a nie tworząc nowego modułu. Walidacja temperatur ma pozostać nienaruszona (jej testy i kontrakt sensora).

**Rejestracja.** Zapis tylko dla wywołań serwisu, w handlerze serwisu (`__init__.py`), nie w `coordinator.async_calculate_forecast_energy`, bo sensory `Scheduled Forecast` wołają koordynator bezpośrednio i nie mają być liczone. Zapisywane: `called_at`, `window_start`, `window_end`, `predicted_kwh`. Czasy okna pochodzą z wyniku kalkulatora (`hours[0].datetime`, `hours[-1].datetime + 1h`), a NIE ze `starting_hour` (kalkulator wybiera pierwszy wpis z `dt >= now` i `dt.hour == starting_hour`, więc okno może wypaść następnego dnia).

**Weryfikacja.** W `window_end` (z krótkim opóźnieniem, ok. 1 min): `actual = stan(window_end) - stan(window_start)` licznika narastającego energii (kWh), odczytanego z Recordera.
- Wartość na granicy: ostatni znany stan nie późniejszy niż granica, bez limitu wieku (Recorder zapisuje tylko zmiany; licznik raportuje co ok. 15 s, ale powtarza wartość przy braku zmiany w rozdzielczości 0,01 kWh). Użyć `include_start_time_state`.
- Błąd kwantyzacji ≤ 0,01 kWh na granicę, ≤ 0,02 kWh na okno.
- Pominięcie oceny z powodem: `no_boundary_reading`, `sensor_unavailable`, ujemna różnica (reset licznika), `recorder_unavailable` po limicie ponowień.
- Wpisy muszą przetrwać restart HA (`Store`); po starcie dosprawdzać wpisy, które dojrzały.
- Okno z brakującymi godzinami prognozy jest pomijane, a nie sumowane częściowo.

**Definicja accuracy.** `accuracy = predicted / actual × 100%`: 100% to dokładna prognoza, 80% niedoszacowanie, 120% przeszacowanie. Przy `actual = 0` wartość niezdefiniowana (`unknown`).

**Deduplikacja.** Jeden wpis na okno (`window_start`/`window_end`); wygrywa najstarsze wywołanie (największy horyzont). Skala: ok. 3–4 wywołania dziennie, nie dla nakładających się okien. Retencja po weryfikacji: 30 dni.

**Horyzont i koszyki.** `horyzont = window_end - called_at`, zaokrąglany w górę do pełnych godzin. Koszyki: do 3 h, 4–6 h, 7–12 h, 13–24 h, powyżej 24 h. Odrzucone: samo `hours_ahead` (ignoruje niepewność wynikającą z wyprzedzenia), jedna liczba zbiorcza, podział po godzinie startu.

**Uwzględnianie poprzednich wyników (EWMA w czasie).** Dwie sumy z wykładniczym zanikiem: `P` (prognozowana energia) i `A` (faktyczna energia). Przy każdej ocenie, w kolejności `window_end`, obie mnożone przez `exp(-ln2 · Δt / T½)` (`Δt` = czas od poprzedniej oceny) i dodawana nowa para. `accuracy = P / A × 100%`. `T½` domyślnie 7 dni, konfigurowalne w opcjach. Ważenie energią jest zamierzone. Odrzucone: średnia ilorazów pojedynczych ocen (obciążona: 200% i 50% dają 125% mimo zrównoważonych błędów).
- Per koszyk własna para `P`/`A` i liczba ocen.
- Wartość agregatu jest pokazywana od 3 ocen i `A > 0`; bez progu energii (błąd kwantyzacji jest bezwzględny, małe okna ważą mało).
- Ostatnia ocena z pojedynczego wpisu: accuracy tylko dla `actual >= 0,2 kWh` (kwantyzacja ≤ 10%), w przeciwnym razie `accuracy: null`, powód `actual_too_small`. Obie wartości (3 oceny, 0,2 kWh) to stałe w kodzie, nie opcje.

**Prezentacja.** Sensor główny: zbiorcza accuracy (EWMA). Atrybuty: średnia z ostatnich N ocen, liczba próbek i efektywna liczba próbek, rozbicie na koszyki, ostatnia ocena (prognoza, faktyczne, accuracy, horyzont). Opis sensora ma jasno mówić, że to dokładność end-to-end (błąd pogody i krzywej mocy), a nie ocena samego modelu.

**Fazowanie specu.** Faza 1: zapis i weryfikacja (dane zbierane od razu). Faza 2: agregacja EWMA, koszyki, sensor, opcja `T½`.

Odrzucone alternatywy: liczenie także wywołań z `Scheduled Forecast`; osobny nowy moduł zamiast rozszerzenia `forecast_validation`; "build nothing". Użytkownik świadomie pominął tani krok zerowy (analiza 2 tygodni historii licznika) i woli poprawiać działający mechanizm.

## Resolved unknowns

| Question | Answer (from the conversation) |
|----------|--------------------------------|
| Co jest oceniane? | Tylko wywołania serwisu `calculate_forecast_energy`; nie wywołania z `Scheduled Forecast` |
| Co z sensorami Scheduled Forecast? | Mają zostać usunięte później (poza zakresem); nowa funkcja nie może od nich zależeć |
| Źródło faktycznego zużycia? | Sensor energii konfiguracji, dedykowany pompie ciepła, licznik narastający kWh, rozdzielczość 0,01 kWh, raport co ok. 15 s; mierzy to samo, co przewiduje algorytm |
| Którego sensora użyć? | Tej samej ścieżki odczytu co uczenie (coordinator czyta dziś tylko z `entry.data`, options flow może go nadpisać) |
| Definicja accuracy? | predicted / actual × 100% |
| Czym jest horyzont? | `window_end - called_at`, zaokrąglony w górę do pełnych godzin |
| Jakie koszyki? | ≤3 h, 4–6 h, 7–12 h, 13–24 h, >24 h |
| Jak uwzględniać historię? | EWMA w czasie na sumach `P`/`A` ważonych energią, `T½` = 7 dni (konfigurowalne) |
| Częstość wywołań i duplikaty? | ok. 3–4 dziennie, nie dla nakładających się okien; jeden wpis na okno, najstarszy wygrywa |
| Odczyt na granicy okna? | Ostatni znany stan ≤ granica, bez limitu wieku; pominięcie przy braku stanu lub `unavailable` |
| Gdzie zaimplementować? | Rozszerzyć `ForecastValidationManager` w `forecast_validation.py` |
| Progi małych wartości? | Agregat: ≥3 oceny i `A > 0`; pojedyncza ocena: `actual >= 0,2 kWh`; stałe w kodzie |
| Retencja? | 30 dni po weryfikacji |
| Krok zerowy (analiza historii)? | Pominięty na życzenie użytkownika |

## Non-goals

- Usunięcie sensorów `Scheduled Forecast`.
- Korekta prognoz ani parametrów algorytmu na podstawie accuracy (to osobna funkcja, jak etap korekty walidacji temperatur).
- Zmiana kontraktu serwisu `calculate_forecast_energy` (pola, wartości i kształt odpowiedzi; zgodnie z `BACKWARD_COMPATIBILITY.md` zmiany tylko addytywne).
- Naprawa rozbieżności `entry.data` vs `options` dla sensora energii, o ile nie jest potrzebna do poprawnego odczytu w walidacji.
- Zmiana zachowania wyboru okna, gdy `starting_hour == now.hour`, pozostawała poza zakresem tej funkcji; późniejsza poprawka może zmienić wybór bez zmiany zasady, że walidacja używa godzin zwróconych przez kalkulator.
- Oceny wywołań z nakładającymi się oknami poza regułą "jedno okno, najstarszy wygrywa".

## Affected areas (if known)

- `custom_components/heat_pump_predictor/forecast_validation.py` (`ForecastValidationManager`, Store, odczyt Recordera)
- `custom_components/heat_pump_predictor/__init__.py` (handler serwisu `calculate_forecast_energy`)
- `custom_components/heat_pump_predictor/coordinator.py` (ścieżka odczytu sensora energii; wynik kalkulatora z czasami okna)
- `custom_components/heat_pump_predictor/forecast_energy.py` (źródło `hours[0]`/`hours[-1]`)
- nowy sensor, opcja `T½`, tłumaczenia (`strings.json`, `translations/`), `README.md`
- Istniejąca walidacja temperatur: `.ai/specs/briefs/2026-11-06-forecast-temperature-validation.md`, `.scratch/forecast-temperature-validation/`
