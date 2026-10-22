# Convenience targets. OpenFOAM v2106 is needed for validate and demo only.
PY ?= python3
POD = Solver_Examples/PODFoam

.PHONY: test evidence links validate runtime demo stop

test:            ## unit tests, no OpenFOAM or model (about 25 s)
	cd $(POD)/llm_demo && $(PY) -m unittest test_llm_client test_callback test_ablation_runner test_async test_picture_test -v

evidence:        ## evidence files match their manifests
	$(PY) docs/evidence/check_manifest.py

links:           ## relative links in docs resolve
	$(PY) docs/check_links.py

validate:        ## bridge validation run (builds PODFoam, ~minutes)
	cd $(POD) && ./validation/run_v2106.sh

runtime:         ## download model + llama.cpp, start the server
	cd $(POD) && ./llm_demo/setup_runtime.sh && $(PY) llm_demo/runtime.py start

demo:            ## five-case demo run and verification
	cd $(POD) && ./llm_demo/run_demo.sh

stop:            ## stop the model server
	cd $(POD) && $(PY) llm_demo/runtime.py stop
