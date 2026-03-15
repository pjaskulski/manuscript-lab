---
title: "Instrukcja obsługi aplikacji Manuscripts Lab"
lang: pl-PL
---

## 1. Cel aplikacji

Manuscripts Lab służy do pracy ze skanami manuskryptów, wariantami odczytu HTR oraz wariantami tłumaczeń. Aplikacja pozwala:

- gromadzić i opisywać skany,
- zapisywać różne wersje tekstu dla pojedynczego skanu,
- porównywać wyniki HTR z tekstem wzorcowym przy użyciu metryk CER i WER,
- łączyć skany w dokumenty,
- budować tekst źródłowy dokumentu na podstawie powiązanych skanów,
- zapisywać warianty tłumaczeń dokumentów,
- porównywać tłumaczenia przy użyciu metryk BLEU i chrF++,
- przeglądać raporty jakości HTR i tłumaczeń.

Instrukcja opisuje obsługę aplikacji z perspektywy użytkownika końcowego.

## 2. Menu główne

W górnym pasku nawigacji dostępne są sekcje:

- `Start` – strona główna z krótkim podsumowaniem liczby skanów i dokumentów.
- `Skany` – baza skanów, ich metadanych oraz wariantów tekstu HTR.
- `Dokumenty` – baza dokumentów złożonych ze skanów oraz tłumaczeń.
- `Parametry` – słowniki modeli HTR i modeli tłumaczeń.
- `Raport jakości HTR` – zbiorczy raport jakości modeli HTR.
- `Raport jakości tłumaczeń` – zbiorczy raport jakości tłumaczeń.

## 3. Zalecana kolejność pracy

Najwygodniejszy sposób pracy z aplikacją wygląda tak:

1. Dodać modele w sekcji `Parametry`.
2. Dodać skan w sekcji `Skany`.
3. Dodać do skanu tekst wzorcowy i jeden lub więcej wyników modelu HTR.
4. Wykonać porównanie HTR dla skanu.
5. W razie potrzeby oznaczyć skan jako element próbki uczącej.
6. Utworzyć dokument w sekcji `Dokumenty`.
7. Powiązać z dokumentem odpowiednie skany.
8. Przebudować tekst źródłowy dokumentu ze skanów.
9. Dodać warianty tłumaczeń i wykonać porównania.
10. Analizować wyniki w raportach jakości.

## 4. Sekcja Parametry

Sekcja `Parametry` służy do prowadzenia słowników modeli. Są tam dwie listy:

- modele HTR,
- modele tłumaczeń.

### Dodawanie modelu

1. Wejdź do `Parametry`.
2. W odpowiedniej kolumnie kliknij `Dodaj model`.
3. Wpisz nazwę modelu.
4. Kliknij `Zapisz`.

### Edycja i usuwanie modelu

- `Edytuj` pozwala zmienić nazwę modelu.
- `Usuń` usuwa model ze słownika.
- Specjalna pozycja odpowiadająca pracy ręcznej może być zablokowana przed usunięciem.

Warto najpierw uzupełnić słownik modeli, ponieważ później te nazwy są wybierane przy dodawaniu tekstów HTR i wariantów tłumaczeń.

## 5. Sekcja Skany

Sekcja `Skany` służy do zarządzania pojedynczymi obrazami skanów oraz ich odczytami tekstowymi.

### Lista skanów

Na liście skanów można:

- filtrować rekordy po tytule, sygnaturze, folio lub ręce,
- sortować listę,
- przechodzić do podglądu skanu,
- edytować metadane,
- przejść do eksportu próbki uczącej,
- dodać nowy skan.

### Dodawanie skanu

1. Otwórz `Skany`.
2. Kliknij `Dodaj skan`.
3. Uzupełnij pola:
   `Tytuł`, `Sygnatura`, `Folio`, `Kolejność`, `Ręka`, `Uwagi`.
4. Opcjonalnie zaznacz:
   `Do próbki uczącej` i `Gotowe`.
5. Opcjonalnie dodaj plik obrazu skanu.
6. Kliknij `Zapisz`.

Obsługiwane są typowe formaty graficzne, m.in. JPG, PNG, WEBP i TIFF.

### Widok pojedynczego skanu

W widoku skanu dostępne są:

- obraz skanu wraz z możliwością pobrania pliku,
- metadane skanu,
- lista wariantów tekstu przypisanych do skanu,
- lista porównań HTR,
- akcje:
  `Edytuj metadane`, `Dodaj tekst`, `Porównaj HTR`, `Usuń skan`.

## 6. Warianty tekstu HTR

Każdy skan może mieć wiele wariantów tekstu, np. tekst wzorcowy i wyniki różnych modeli.

### Dodawanie tekstu do skanu

1. Otwórz wybrany skan.
2. Kliknij `Dodaj tekst`.
3. Uzupełnij pola:
   - `Typ tekstu`
   - `Model`
   - `Uwagi`
   - `Treść`
4. W razie potrzeby zaznacz:
   - `Podstawowa wersja ground truth`
   - `Tekst poliniowany`
5. Kliknij `Zapisz`.

### Typy tekstu

Dostępne typy to:

- `Ground truth`
- `Ground truth, zapis dyplomatyczny`
- `Ground truth, zapis rozwinięty`
- `Wynik modelu HTR`

Jeżeli dany tekst ma być podstawowym tekstem wzorcowym dla skanu i dla eksportu próbki uczącej, należy oznaczyć go jako `Podstawowa wersja ground truth`.

### Edycja tekstu i workspace

Przy każdym wariancie tekstu dostępne są akcje:

- `HTR` – otwiera przestrzeń roboczą do wygodnej korekty treści,
- `Edytuj` – otwiera formularz metadanych i treści,
- `Usuń` – usuwa wariant tekstu.

## 7. Porównania HTR

Porównania HTR wykonuje się na poziomie pojedynczego skanu.

### Jak wykonać porównanie HTR

1. Otwórz skan.
2. Kliknij `Porównaj HTR`.
3. Wybierz:
   - `Tekst wzorcowy`
   - `Tekst porównywany`
   - `Profil normalizacji`
4. Kliknij `Porównaj`.

### Profile normalizacji

Dostępne profile:

- `raw` – bez normalizacji,
- `lowercase` – zapis małymi literami,
- `lowercase_no_punct` – małe litery bez interpunkcji.

### Co pokazuje wynik porównania HTR

Widok szczegółów porównania pokazuje:

- metrykę `CER`,
- metrykę `WER`,
- użyty profil normalizacji,
- źródła porównania,
- wizualizację różnic między tekstem wzorcowym i porównywanym.

Jeżeli porównanie zostało otwarte z raportu jakości HTR, przycisk powrotu prowadzi z powrotem do raportu. Jeśli zostało otwarte z widoku skanu, przycisk prowadzi do skanu.

## 8. Raport jakości HTR

Raport jakości HTR prezentuje zbiorczą ocenę modeli HTR na podstawie zapisanych porównań.

### Jak działa raport

Raport:

- grupuje porównania według modelu i profilu normalizacji,
- przelicza metryki `CER` i `WER` dla całego zbioru porównań w grupie,
- pokazuje liczbę porównań i liczbę skanów w danej grupie.

### Jak czytać raport

W sekcji `Lista modeli` znajdują się:

- `Model`
- `Normalizacja`
- `Porównania`
- `Skany`
- `CER zbiorcze`
- `WER zbiorcze`

Kliknięcie `Skład` przy wybranym modelu otwiera sekcję `Lista porównywanych skanów`, w której widać:

- identyfikator porównania,
- skan,
- wynik `CER` dla skanu,
- wynik `WER` dla skanu,
- link `Szczegóły`.

Raport służy przede wszystkim do porównywania jakości modeli HTR między sobą.

## 9. Eksport próbki uczącej

Sekcja `Skany` zawiera funkcję `Eksport próbki uczącej`.

### Kiedy skan trafi do eksportu

Do eksportu zostaną uwzględnione tylko te skany, które:

- są oznaczone jako `Do próbki uczącej`,
- mają przypisany obraz,
- mają wskazaną `Podstawową wersję ground truth`.

### Jak wykonać eksport

1. Otwórz `Skany`.
2. Kliknij `Eksport próbki uczącej`.
3. Sprawdź liczbę skanów gotowych do eksportu.
4. Opcjonalnie zaznacz `Dołącz pliki skanów`.
5. Kliknij `Przygotuj paczkę ZIP`.

W wyniku zostanie pobrany plik ZIP z tekstami ground truth, a opcjonalnie także z obrazami.

## 10. Sekcja Dokumenty

Dokument to logiczna jednostka złożona z jednego lub wielu skanów. W tej sekcji można też prowadzić warianty tłumaczeń.

### Dodawanie dokumentu

1. Otwórz `Dokumenty`.
2. Kliknij `Dodaj dokument`.
3. Uzupełnij:
   - `Tytuł`
   - `Sygnatura źródła`
   - `Uwagi`
   - opcjonalnie `Tekst źródłowy`
   - opcjonalnie `Gotowe`
4. Kliknij `Zapisz`.

### Widok dokumentu

Widok dokumentu zawiera:

- metadane,
- listę powiązanych skanów,
- tekst źródłowy dokumentu,
- listę wariantów tłumaczeń,
- listę porównań tłumaczeń.

Dostępne akcje:

- `Edytuj metadane`
- `Powiąż skan`
- `Dodaj wariant tłumaczenia`
- `Porównaj tłumaczenia`
- `Przebuduj tekst źródłowy ze skanów`
- `Usuń dokument`

### Powiązywanie skanów z dokumentem

1. Otwórz dokument.
2. Kliknij `Powiąż skan`.
3. Wybierz skan.
4. Ustaw jego `Kolejność`.
5. Kliknij `Zapisz`.

Kolejność ma znaczenie przy budowie tekstu źródłowego dokumentu.

### Przebudowa tekstu źródłowego

Przycisk `Przebuduj tekst źródłowy ze skanów` tworzy lub aktualizuje tekst źródłowy dokumentu na podstawie powiązanych skanów i ich treści.

Z tej funkcji warto skorzystać po:

- dodaniu nowych skanów do dokumentu,
- zmianie kolejności skanów,
- poprawkach w tekstach HTR lub ground truth.

## 11. Warianty tłumaczeń

Do każdego dokumentu można dodać wiele wariantów tłumaczeń.

### Dodawanie wariantu tłumaczenia

1. Otwórz dokument.
2. Kliknij `Dodaj wariant tłumaczenia`.
3. Uzupełnij:
   - `Typ wariantu`
   - `Model`
   - `Uwagi`
   - `Treść`
4. Kliknij `Zapisz`.

### Typy wariantów tłumaczeń

Dostępne typy:

- `Referencyjne`
- `Wynik modelu`

### Edycja wariantów

Przy każdym wariancie dostępne są akcje:

- `Edytuj`
- `Usuń`

## 12. Porównania tłumaczeń

Porównania tłumaczeń wykonuje się na poziomie pojedynczego dokumentu.

### Jak wykonać porównanie tłumaczeń

1. Otwórz dokument.
2. Kliknij `Porównaj tłumaczenia`.
3. Wybierz wariant referencyjny i wariant porównywany.
4. Opcjonalnie dodaj uwagi.
5. Kliknij `Porównaj`.

### Co pokazuje wynik

Widok szczegółów porównania tłumaczeń pokazuje:

- `BLEU`
- `chrF++`
- tekst wzorcowy,
- tekst porównywany.

## 13. Raport jakości tłumaczeń

Raport jakości tłumaczeń agreguje zapisane porównania tłumaczeń dla całych korpusów dokumentów.

W raporcie można zobaczyć:

- grupy porównań,
- liczbę porównań i dokumentów,
- `BLEU korpusowe`,
- `chrF++ korpusowe`,
- skład danej grupy.

Wyniki są liczone ponownie dla całego zbioru porównań, a nie jako średnia z dokumentów.

## 14. Oznaczenia i dobre praktyki

### Oznaczenie `Gotowe`

Pole `Gotowe` występuje przy skanach i dokumentach. Można go używać jako znacznika zakończenia prac nad danym rekordem.

### Oznaczenie `Do próbki uczącej`

To pole należy zaznaczać tylko wtedy, gdy skan ma być uwzględniony w eksporcie materiałów treningowych.

### Podstawowa wersja ground truth

Dla jednego skanu warto wskazać jedną podstawową wersję ground truth. To ona jest używana przy eksporcie próbki uczącej.

### Sugerowany model pracy

- Najpierw wprowadź model do słownika.
- Potem dodaj skan i tekst wzorcowy.
- Następnie dodaj wynik modelu HTR.
- Dopiero potem wykonaj porównania i analizę raportów.

## 15. Najczęstsze sytuacje

### Nie widać modelu na liście wyboru

Najpierw dodaj go w sekcji `Parametry`.

### Skan nie trafia do eksportu próbki uczącej

Sprawdź, czy:

- zaznaczono `Do próbki uczącej`,
- dodano obraz skanu,
- istnieje podstawowa wersja ground truth.

### Raport jakości HTR jest pusty

Raport pokazuje tylko zapisane porównania HTR. Najpierw trzeba wykonać porównania dla co najmniej jednego skanu.

### Raport jakości tłumaczeń jest pusty

Najpierw trzeba dodać warianty tłumaczeń i zapisać porównania dla dokumentów.

## 16. Podsumowanie

Aplikacja wspiera dwa główne obszary pracy:

- analizę jakości HTR na poziomie skanów i zbiorów skanów,
- analizę jakości tłumaczeń na poziomie dokumentów i korpusów.

Najlepsze efekty daje konsekwentne uzupełnianie:

- metadanych,
- nazw modeli,
- tekstów wzorcowych,
- wyników modeli,
- zapisanych porównań.
