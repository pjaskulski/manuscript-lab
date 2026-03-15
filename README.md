# Manuscripts Lab — 

Prototyp aplikacji do pracy ze skanami manuskryptów (HTR) oraz tłumaczeniem dokumentów.

## Zakres MVP

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
