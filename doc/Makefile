
BASEDIR=$(CURDIR)
DOCDIR=$(BASEDIR)/content
OUTPUTDIR=$(BASEDIR)/output
THEMEDIR=$(BASEDIR)/theme

html:
	quaint site $(DOCDIR) -f $(OUTPUTDIR) -x "use_theme(/theme)"
	cp -r $(THEMEDIR) $(OUTPUTDIR)

clean:
	rm -rf $(OUTPUTDIR)
