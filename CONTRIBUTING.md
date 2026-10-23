# Contributing

Start with a reproducible pair of **synthetic** tool snapshots and the expected finding. Please exclude credentials, private tool descriptions, and customer data.

Run locally with Python 3.10 or later:

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

For changes to compatibility rules, add a focused regression test and update `docs/rules.md`. Prefer a conservative `review` finding when JSON Schema semantics cannot be established. Do not add automatic server execution or network access to the comparison path.

Pull requests should explain the before/after behavior and relevant validation. No external services or paid API keys are required to run tests.
