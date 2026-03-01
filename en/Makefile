all: *.tex *.bib
	pdflatex main
	-bibtex main
	makeindex main
	pdflatex main
	pdflatex main

clean:
	rm -f *.aux *.bbl *.blg *.dvi *.log *.toc *.idx *.ilg *.ind *.out *.fdb_latexmk *.fls

cleanAll:
	rm -f *.pdf *.aux *.bbl *.blg *.dvi *.log *.toc *.idx *.ilg *.ind *.out *.fdb_latexmk *.fls
