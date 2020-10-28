INPUTDOTS := graph/bootstrap.dot graph/xandr-integration.dot

graph/terraform.pdf:

graph/terraform.dot: $(INPUTDOTS) collect_graphs.py
	./collect_graphs.py $(INPUTDOTS) > $@

%.pdf: %.dot
	dot -Tpdf -o $@ $<
