
## Architektura aplikacji

**Manuscript Lab** jest monolityczną aplikacją internetową zbudowaną z użyciem frameworka **Flask**, zaprojektowaną w układzie warstwowym. Struktura aplikacji obejmuje: warstwę obsługi żądań HTTP i widoków opartą na mechanizmie **Blueprints**, warstwę modeli danych wykorzystującą **ORM SQLAlchemy**, warstwę usług pomocniczych (**services**) odpowiedzialną za logikę wspólną i operacje pomocnicze oraz warstwę prezentacji opartą na silniku szablonów **Jinja2**.

Punktem wejścia aplikacji jest plik `run.py`, natomiast właściwa inicjalizacja odbywa się w fabryce aplikacji `create_app()` zdefiniowanej w `app/__init__.py`. Na tym etapie ładowana jest konfiguracja z modułu `app/config.py`, tworzony jest katalog `instance/`, inicjalizowane są komponenty infrastrukturalne, takie jak **SQLAlchemy**, **Flask-Migrate** oraz **Flask-Login**, a następnie rejestrowane są blueprinty i globalne procedury obsługi błędów.

Istotnym elementem architektury jest zastosowanie middleware `ProxyFix`, co oznacza, że aplikacja została przygotowana do pracy za pośrednictwem **reverse proxy**. Dodatkowo podczas uruchamiania system potrafi samodzielnie uzupełniać wybrane braki w schemacie bazy danych SQLite, zamiast opierać się wyłącznie na migracjach. Obejmuje to między innymi dodawanie brakujących kolumn oraz przebudowę ograniczenia unikalności w tabeli `documents`. Rozwiązanie to wskazuje na pragmatyczny charakter projektu: migracje pozostają podstawowym mechanizmem ewolucji schematu, jednak kod startowy zapewnia również zgodność ze starszymi wersjami bazy danych.

## Model domenowy

Model danych aplikacji opiera się na trzech podstawowych bytach domenowych.

Encja **Scan** reprezentuje pojedynczy skan i przechowuje zarówno jego metadane, jak i ścieżkę do powiązanego pliku graficznego. Z jednym skanem może być związanych wiele wariantów tekstu, reprezentowanych przez model **ScanText**, a także wiele porównań wyników HTR, realizowanych przez model **HTRComparison**.

Encja **Document** pełni rolę obiektu wyższego poziomu, agregującego wiele skanów za pośrednictwem tabeli pośredniczącej **DocumentScanLink**. Przechowuje ona również scalony tekst źródłowy w polu `original_text`, a ponadto wiąże z dokumentem warianty tłumaczeń i porównania tych tłumaczeń.

Modele **TranslationVariant** oraz **TranslationComparison** realizują wzorzec analogiczny do tego, który zastosowano w module HTR, lecz odnoszą go do procesu tłumaczenia.

Uzupełnieniem modelu domenowego jest niewielki moduł konfiguracyjny, obejmujący encje **ParameterModel** oraz **ParameterPrompt**. Nie pełnią one funkcji technicznych ustawień aplikacji, lecz stanowią słowniki biznesowe wykorzystywane w formularzach dotyczących HTR i tłumaczeń. Autoryzacja użytkowników oparta jest natomiast na prostym modelu **User**, przechowującym skrót hasła.

## Warstwa HTTP i organizacja modułów

Warstwa HTTP została podzielona na blueprinty odpowiadające podstawowym obszarom funkcjonalnym aplikacji.

Blueprint **scans** odpowiada za pełny cykl operacji CRUD na skanach, import masowy, eksport próbek uczących, a także serwowanie plików i miniaturek.

Blueprint **htr** obsługuje zarządzanie wariantami transkrypcji, środowisko robocze do ręcznej korekty, porównania jakości z wykorzystaniem miar **CER** i **WER**, a także raport korpusowy. Moduł ten zawiera również endpoint AJAX służący do dopasowywania linii tekstu z użyciem modelu **Google Gemini**.

Blueprint **documents** integruje informacje o dokumencie, listę powiązanych skanów, warianty tłumaczeń oraz ich porównania. Udostępnia także mechanizm rekonstrukcji pola `original_text` na podstawie tekstów przypisanych do skanów.

Blueprint **translations** odpowiada za operacje CRUD na wariantach tłumaczeń, porównania z użyciem metryk **BLEU** i **chrF++** oraz raport korpusowy dla tłumaczeń.

Blueprint **parameters** pełni funkcję panelu administracyjnego dla słowników modeli i promptów. Z kolei moduły **auth** oraz **main** realizują funkcje podstawowe: odpowiednio logowanie użytkowników oraz obsługę głównego panelu startowego.

## Przepływ danych i logika aplikacyjna

Przepływ danych w aplikacji został zaprojektowany jako sekwencja kolejnych etapów pracy badawczej. Proces rozpoczyna się na poziomie skanów: użytkownik dodaje obrazy, przypisuje im różne warianty tekstu, a następnie porównuje jakość wyników HTR. W dalszej kolejności skany są łączone w dokument, na podstawie którego budowany jest tekst źródłowy. Ostatnim etapem jest dodawanie do dokumentu wariantów tłumaczeń oraz ich wzajemne porównywanie.

Logika wspólna dla poszczególnych modułów została wydzielona do warstwy `services`. Moduł **file_storage** odpowiada za zapis plików graficznych i generowanie miniaturek. Moduł **htr_metrics** oblicza miary **CER** i **WER**, a także generuje różnicowy podgląd HTML wykorzystywany w widokach porównań. Analogiczną funkcję dla tłumaczeń pełni moduł **bleu_metrics**. Usługa **gemini_alignment** integruje aplikację z API modelu Gemini i zwraca sformatowany tekst wyrównany linia po linii. Moduł **model_registry** udostępnia dynamiczne listy modeli i promptów do wykorzystania w formularzach.

Istotnym rozwiązaniem architektonicznym jest mechanizm ochrony przed nadpisaniem zmian w środowisku wieloużytkownikowym. Moduł **concurrency** realizuje uproszczoną formę **optimistic locking**, porównując wartość pola `updated_at` z ukrytym `version_token` przesyłanym w formularzu. Oznacza to, że aplikacja nie stosuje blokad rekordów na poziomie bazy danych, lecz wykrywa konflikt na poziomie formularza i obsługuje go za pomocą globalnego mechanizmu błędów.

## Warstwa prezentacji

Warstwa frontendowa ma charakter prosty i jest w całości oparta na **renderowaniu po stronie serwera**. Wspólny układ strony, menu nawigacyjne, arkusze stylów CSS oraz komunikaty typu flash zostały zorganizowane w szablonach Jinja2. Większość operacji realizowana jest w klasycznym modelu formularzy HTTP `POST` i renderowanych odpowiedzi HTML. Wyjątek stanowią pojedyncze interakcje asynchroniczne, takie jak funkcja `align-lines` w module HTR.

Takie podejście sprzyja utrzymaniu przejrzystości kodu i ogranicza złożoność warstwy klienckiej. W praktyce każdy moduł funkcjonalny posiada zwykle własny zestaw plików `forms.py`, `routes.py` oraz odpowiadających im szablonów domenowych.

## Podsumowanie

Najkrócej rzecz ujmując, **Manuscript Lab** jest serwerowo renderowaną aplikacją Flask typu **CRUD + workflow**, zaprojektowaną na potrzeby badań nad rękopisami. Encja **Scan** pełni w niej rolę podstawowego bytu źródłowego, natomiast **Document** stanowi agregat wyższego poziomu. Moduły HTR i tłumaczeń tworzą dwie równoległe ścieżki analityczne, oparte na wspólnym wzorcu organizacyjnym: **wariant – porównanie – raport korpusowy**.

