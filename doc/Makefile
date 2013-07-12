
BASEDIR=$(CURDIR)
DOCDIR=$(BASEDIR)/content
OUTPUTDIR=$(BASEDIR)/output
THEMEDIR=$(BASEDIR)/theme
URL=/

html: theme
	quaint site $(DOCDIR) -o $(OUTPUTDIR) -x "use_theme($(URL)theme)" -e "siteroot: '$(URL)'"

theme: output
	cp -r $(THEMEDIR) $(OUTPUTDIR)

output:
	mkdir output

clean:
	rm -rf $(OUTPUTDIR)

.PHONY: theme
