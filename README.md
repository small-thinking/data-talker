# data-talker
Talk with your data in the human way.

## How to use
### Configure environment
```bash
mv .env.template .env
```

### Manual Setup
You should have conda installed in your system. If not, you can install it from [here](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html).

Then run:
```bash
./setup.sh
```
This will install poetry and create a virtual environment.

Run the following to start the backend:
```bash
poetry run python data_talker/service.py
```
