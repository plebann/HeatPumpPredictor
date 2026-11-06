# Zaprojektuj etap 1 walidacji temperatur prognozy

- Date: 2026-11-06
- Category: feature
- Priority signal: medium — użytkownik potrzebuje danych o jakości prognoz temperatury, zanim podejmie decyzję o korekcie prognoz energii.
- Risk signal: medium — błędnie zdefiniowana metryka mogłaby przedstawiać różnicę semantyki danych jako błąd prognozy.
- Routing: Next: om-spec-writing "Zaprojektuj etap 1 walidacji temperatur prognozy — brief: .ai/specs/briefs/2026-11-06-forecast-temperature-validation.md"

## Problem

Heat Pump Predictor nadpisuje w pamięci cache godzinowej prognozy pogody, więc po upływie celu prognozy użytkownik nie może ustalić, czy i jak dokładnie temperatura prognozowana różniła się od temperatury zarejestrowanej przy obserwowanej pompie ciepła. Użytkownik chce trwałej, ograniczonej retencją obserwacji tych różnic i diagnostyki per horyzont pobrania, zanim jakakolwiek korekta wpłynie na prognozy energii. Aktualny brak tych danych uniemożliwia ocenę, czy lokalny, stabilny błąd temperatury jest wystarczająco istotny, by uzasadniać późniejszą korektę.

## Agreed direction

Podzielić obecne GitHub issue #2 na niezależny etap 1 obserwacji oraz przyszły etap ręcznej korekty. Etap 1 zapisuje niezmienne snapshoty prognozy, waliduje kompletne godziny na podstawie historii Recorder i udostępnia zagregowaną diagnostykę bez zmieniania istniejących prognoz energii. Dla każdej kombinacji źródła, docelowego okna godzinowego oraz przedziału horyzontu do metryk kwalifikuje się ostatni snapshot pobrany przed początkiem tego okna; pełne dane pozostają dostępne do audytu w okresie retencji.

Zachować rzeczywistą temperaturę jako średnią ważoną czasem w oknie `[target_at, target_at + 1h)`, ale jawnie raportować porównanie z punktową temperaturą źródłową jako „różnicę prognozy punktowej względem średniej godzinnej”. Nie przedstawiać tej wartości jako gotowego do zastosowania biasu ani nie zmieniać korekty energii. Odrzucono czekanie z całą pracą do rozstrzygnięcia korekty, ponieważ same dane walidacyjne mają niezależną wartość. Odrzucono także brak zmian, ponieważ obecny nadpisywany cache nie pozwala później odtworzyć oceny.

## Resolved unknowns

| Question | Answer (from the conversation) |
|----------|--------------------------------|
| Gdzie prowadzić bieżącą pracę trackerową? | GitHub issue #2 jest świadomym wyjątkiem od lokalnego trackera repozytorium: ma zostać zaktualizowane, a przyszła praca ma otrzymać nowe GitHub issue. |
| Co obejmuje etap 1? | Snapshoty, walidacja godzinowa, retencja, deterministyczne deduplikowanie oraz horyzontowa diagnostyka; bez stosowania korekty temperatury lub energii. |
| Który snapshot reprezentuje targetowe okno w metrykach? | Ostatni kwalifikujący się snapshot pobrany przed początkiem okna, jeden na `(weather entity, target window, horizon range)`. |
| Jaka jest definicja rzeczywistej temperatury? | Średnia ważona czasem z historii Recorder dla pełnego okna `[target_at, target_at + 1h)`, z uwzględnieniem stanu obowiązującego na początku. |
| Jak traktować brakujące i wadliwe dane? | Wykluczać `unknown`, `unavailable`, wartości nienumeryczne i niekończone; nie przedłużać poprzedniej wartości przez znany niedostępny okres. Walidacja wymaga co najmniej 60% pokrycia poprawnymi danymi, w przeciwnym razie pozostaje niezwalidowana z powodem. |
| Jak interpretować porównanie punktowej prognozy z godzinowym pomiarem? | Jako diagnostyczną różnicę prognozy punktowej względem średniej godzinnej, nie jako zatwierdzony bias do korekty. |
| Jaki jest okres metryk? | Ostatnie 14 dni według `target_at`; gdy historia jest krótsza, cała dostępna historia. Metryki są publikowane od pierwszej próbki i zawsze zawierają liczbę unikalnych okien. |
| Jaka jest retencja surowych danych? | 28 dni dla snapshotów i wyników walidacji. |
| Czy korekta ma się aktywować automatycznie? | Nie. Korekta nie należy do etapu 1, a przyszła funkcja ma pozostać ręcznie włączana i domyślnie wyłączona. |

## Non-goals

- Wprowadzanie, aktywowanie lub ocenianie korekty temperatur wejściowych albo końcowej prognozy energii.
- Zmiana zachowania istniejącej usługi `calculate_forecast_energy` lub zaplanowanych sensorów.
- Traktowanie prognozy punktowej jako godzinowej średniej bez jawnie zaprojektowanej transformacji.
- Ocena dokładności końcowych prognoz kWh, shadow forecasts lub porównanie baseline-versus-corrected energy.
- Modyfikowanie źródłowego sensora temperatury, surowych snapshotów albo historycznych bucketów pompy ciepła.

## Affected areas (if known)

- `custom_components/heat_pump_predictor/coordinator.py`
- `custom_components/heat_pump_predictor/sensors/forecast_cache.py`
- `custom_components/heat_pump_predictor/forecast_energy.py`
- `tests/test_forecast_energy_calculator.py`
- GitHub issue #2: `https://github.com/plebann/HeatPumpPredictor/issues/2`
