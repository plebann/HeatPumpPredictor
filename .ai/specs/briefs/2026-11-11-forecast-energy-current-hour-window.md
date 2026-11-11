# Napraw wybór bieżącego okna godzinowego prognozy energii

- Date: 2026-11-11
- Category: bug
- Priority signal: medium — opóźnienie automatyzacji o sekundę przesuwa prognozę o dobę albo kończy wywołanie błędem braku danych
- Risk signal: medium — zmiana koryguje publicznie obserwowalny wybór okna i musi poprawnie obsłużyć lokalne strefy czasowe oraz DST
- Routing: Next: om-auto-create-pr "Napraw wybór bieżącego okna godzinowego prognozy energii — brief: .ai/specs/briefs/2026-11-11-forecast-energy-current-hour-window.md"

## Problem

`ForecastEnergyCalculator` wybiera pierwszy wpis, którego czas jest nie wcześniejszy niż dokładny moment wywołania i którego lokalna godzina odpowiada `starting_hour`. W efekcie wywołanie o 06:01 z `starting_hour=6` i `hours_ahead=2` pomija rozpoczęty o 06:00 koszyk i wybiera 06:00–08:00 następnego dnia albo zwraca błąd zbyt krótkiej prognozy. Zostało to odtworzone deterministycznie; oczekiwanym znaczeniem `starting_hour` jest pełny lokalny koszyk godzinowy, a nie pierwsze wystąpienie godziny po dokładnym czasie wywołania.

## Agreed direction

Zmienić wybór okna we wspólnym `ForecastEnergyCalculator`, aby wywołanie w trakcie żądanej godziny wybierało aktualnie trwający pełny koszyk. Dla pierwszej bieżącej godziny korekta trendu ma użyć `current_temperature`; gdy aktualna temperatura jest niedostępna, pierwsza godzina jest liczona bez korekty trendu. Przy jesiennym cofnięciu zegara wybierane ma być aktualnie trwające wystąpienie powtórzonej godziny, z zachowaniem informacji `fold`; przy nieistniejącej godzinie podczas wiosennej zmiany czasu pozostaje wyszukanie następnego dostępnego wystąpienia.

Zachować kształt publicznej odpowiedzi i zaktualizować dokumentację, która opisuje starą regułę „pierwszego przyszłego wpisu”. Dodać kontraktowe testy granic czasu lokalnego, w tym dokładnie 06:00, 06:01, 06:59:59, 07:00, konwersję strefy i oba przypadki DST. Istniejące Scheduled Forecasts zwykle uruchamiają się przed swoim oknem, więc ich standardowe wyniki nie powinny się zmienić.

Odrzucono krótką tolerancję jako arbitralną, proporcjonalne liczenie pozostałej części godziny jako sprzeczne z semantyką pełnego koszyka, nowy parametr pełnej daty i czasu jako nieproporcjonalne rozszerzenie publicznego kontraktu oraz pozostawienie błędu i przesuwanie harmonogramów przed pełną godzinę jako rozwiązanie podatne na opóźnienia automatyzacji.

## Resolved unknowns

| Question | Answer (from the conversation) |
|----------|--------------------------------|
| Jak długo po początku godziny wybierać bieżący koszyk? | Przez całą godzinę, od 06:00 do 06:59:59 dla `starting_hour=6`. |
| Czy wynik bieżącej godziny jest pełny czy częściowy? | Pełny koszyk 06:00–07:00, nawet przy wywołaniu pod koniec godziny. |
| Co dzieje się dokładnie o 07:00 dla `starting_hour=6`? | Bieżący koszyk 06:00–07:00 już się zakończył; należy wyszukać następne wystąpienie godziny 06:00. |
| Które wystąpienie wybrać podczas jesiennego powtórzenia godziny? | Aktualnie trwające wystąpienie; pierwsze 02:xx wybiera pierwszy koszyk, drugie 02:xx drugi. |
| Co zrobić z nieistniejącą godziną podczas wiosennego DST? | Zachować wyszukanie następnego dostępnego wystąpienia żądanej godziny. |
| Jaka temperatura zasila korektę trendu pierwszej bieżącej godziny? | `current_temperature`, a nie prognoza z poprzedniej godziny. |
| Co zrobić bez `current_temperature`? | Policzyć bazową energię pierwszej godziny bez korekty trendu; nie zwracać błędu i nie używać poprzedniej prognozy. |
| Czy zmieniać publiczną odpowiedź serwisu? | Nie; pola, wartościowe typy i kształt odpowiedzi pozostają bez zmian, zmienia się celowo wybór okna. |

## Non-goals

- Proporcjonalne liczenie energii tylko dla pozostałej części rozpoczętej godziny.
- Dodanie parametru pełnej daty lub czasu rozpoczęcia do publicznego serwisu.
- Implementacja lub rozszerzenie funkcji forecast energy accuracy; przyszła walidacja nadal powinna brać granice z godzin zwróconych przez kalkulator.
- Zmiana harmonogramów istniejących sensorów Scheduled Forecast.
- Ogólna przebudowa parsowania prognozy lub modelu korekty trendu poza pierwszą bieżącą godziną.

## Affected areas (if known)

- `custom_components/heat_pump_predictor/forecast_energy.py` — wybór okna i temperatura bazowa pierwszej bieżącej godziny.
- `tests/test_forecast_energy_calculator.py` — regresja i granice czasu lokalnego/DST.
- Dokumentacja kontraktu `starting_hour`, w tym wymagania opisujące dziś „pierwszy przyszły wpis”.
