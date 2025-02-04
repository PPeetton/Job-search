OS := $(shell uname)

ifeq ($(OS), Windows_NT)
    ACTIVATE = venv\Scripts\activate
    RM = rmdir /s /q venv
else
    ACTIVATE = source venv/bin/activate
    RM = rm -rf venv
endif

setup:
	python -m venv venv
	$(ACTIVATE) && pip install --upgrade pip && pip install -r requirements.txt

run:
	# Ensure activation persists in a single shell session
	bash -c "$(ACTIVATE) && python index.py"

install:
	bash -c "$(ACTIVATE) && pip install -r requirements.txt"

lint:
	bash -c "$(ACTIVATE) && flake8 ."

clean:
	$(RM)
