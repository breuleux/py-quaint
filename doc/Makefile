
BASEDIR=$(CURDIR)
DOCDIR=$(BASEDIR)/content
OUTPUTDIR=$(BASEDIR)/output
ASSETSDIR=$(BASEDIR)/assets
URL=/

html: assets
	quaint site $(DOCDIR) -o $(OUTPUTDIR) -x "use_assets($(URL)assets),siteroot($(URL))"

assets: output
	cp -r $(ASSETSDIR) $(OUTPUTDIR)

output:
	mkdir output

clean:
	rm -rf $(OUTPUTDIR)

.PHONY: assets
