all: *.tex *.bib
	-platex -interaction=nonstopmode main
	-pbibtex main
	-makeindex main
	-platex -interaction=nonstopmode main
	-platex -interaction=nonstopmode main
	dvipdfmx main.dvi

clean:
	rm -f *.aux *.bbl *.blg *.dvi *.log *.toc *.idx *.ilg *.ind *.out *.fdb_latexmk *.fls

cleanAll:
	rm -f *.pdf *.aux *.bbl *.blg *.dvi *.log *.toc *.idx *.ilg *.ind *.out *.fdb_latexmk *.fls
