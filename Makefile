.PHONY: install data data-openmeteo run test demo
install:        ; pip install -e ".[gee,openmeteo,dev]"
data:           ; heatcast fetch --source gee
data-openmeteo: ; heatcast fetch --source openmeteo
run:            ; heatcast run
test:           ; pytest -q
demo:           ; heatcast all --source synthetic
