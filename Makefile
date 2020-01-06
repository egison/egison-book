all: *.tex *.bib
	platex main
	-pbibtex main
	makeindex main
	platex main
	platex main
	dvipdfmx main.dvi

clean:
	rm *.aux *.bbl *.blg *.dvi *.log *.toc *.idx *.ilg *.ind

cleanAll:
	rm *.pdf *.aux *.bbl *.blg *.dvi *.log *.toc *.idx *.ilg *.ind
