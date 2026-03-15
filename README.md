# Manuscripts Lab 

Prototyp aplikacji do pracy ze skanami manuskryptów (HTR) oraz tłumaczeniem dokumentów.

### Moduł „Skany”
- dodawanie i edycja definicji skanów,
- upload obrazu skanu,
- dodawanie tekstów typu `ground_truth` i `model_output`,
- porównanie dwóch wariantów tekstu dla skanu,
- obliczanie CER i WER,
- generowanie prostego diff dla wariantów tekstów z HTR.

### Moduł „Dokumenty”
- dodawanie i edycja dokumentów,
- wiązanie dokumentu ze skanami,
- przechowywanie tekstu źródłowego i tłumaczenia referencyjnego,
- dodawanie wariantów tłumaczenia,
- porównanie dwóch wariantów tłumaczenia,
- obliczanie BLEU i chrF.

## Wymagania
- Python 3.11+
- SQLite

## Zrzuty ekranu

![screeenshot](doc/01.png)

![screeenshot](doc/02.png)

![screeenshot](doc/03.png)

![screeenshot](doc/04.png)

![screeenshot](doc/05.png)

![screeenshot](doc/06.png)

![screeenshot](doc/07.png)

![screeenshot](doc/08.png)

![screeenshot](doc/09.png)

![screeenshot](doc/10.png)

![screeenshot](doc/11.png)

![screeenshot](doc/12.png)

![screeenshot](doc/13.png)

![screeenshot](doc/14.png)

![screeenshot](doc/15.png)

## Instalacja

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Uruchomienie

```bash
flask --app run.py shell
```

Utworzenie bazy:

```bash
flask --app run.py db init
flask --app run.py db migrate -m "init"
flask --app run.py db upgrade
```

Start aplikacji:

```bash
python run.py
```

## Struktura

```text
app/
  blueprints/
  models/
  services/
  templates/
  static/
instance/
  uploads/scans/
run.py
requirements.txt
README.md
```

## Uwagi
- obrazy skanów są zapisywane na dysku w `instance/uploads/scans/`,
- baza SQLite jest wystarczająca dla prototypu i małego zespołu
