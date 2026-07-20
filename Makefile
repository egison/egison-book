.PHONY: all html tex tex-en tex-ja clean

all: html tex

html:
	python3 scripts/build_html.py

tex: tex-en tex-ja

tex-en:
	$(MAKE) -C tex/en

tex-ja:
	$(MAKE) -C tex/ja

clean:
	$(MAKE) -C tex/en clean
	$(MAKE) -C tex/ja clean
