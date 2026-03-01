all: *.tex *.bib
	platex main
	-pbibtex main
	makeindex main
	platex main
	platex main
	dvipdfmx main.dvi

clean:
	rm -f *.aux *.bbl *.blg *.dvi *.log *.toc *.idx *.ilg *.ind *.out *.fdb_latexmk *.fls

cleanAll:
	rm -f *.pdf *.aux *.bbl *.blg *.dvi *.log *.toc *.idx *.ilg *.ind *.out *.fdb_latexmk *.fls
