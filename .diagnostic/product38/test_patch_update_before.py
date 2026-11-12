"""Finite public API diagnosis; all Dash implementation comes from the pin."""

import json
import platform
from urllib.parse import urlparse

import pytest
import selenium

import dash
from dash import Dash, Input, Output, Patch, dcc, html
from dash._utils import to_json
from dash.testing.wait import until


MODES = ("shared_mapping", "distinct_mapping", "keyword_only")


def make_patch(mode):
    common = {"currency": "USD"}
    patch = Patch()
    if mode == "shared_mapping":
        patch["jan"].update(common, amount=100)
        patch["feb"].update(common, amount=200)
    elif mode == "distinct_mapping":
        patch["jan"].update(dict(common), amount=100)
        patch["feb"].update(dict(common), amount=200)
    elif mode == "keyword_only":
        patch["jan"].update(currency=common["currency"], amount=100)
        patch["feb"].update(currency=common["currency"], amount=200)
    else:
        raise ValueError(mode)
    return patch, common


@pytest.fixture(scope="session", autouse=True)
def print_versions():
    print(
        "ACTUAL_RUNTIME "
        + json.dumps(
            {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "dash": dash.__version__,
                "dash_import": dash.__file__,
                "selenium": selenium.__version__,
            },
            sort_keys=True,
        ),
        flush=True,
    )


@pytest.mark.parametrize("mode", MODES)
def test_public_producer(mode):
    patch, common = make_patch(mode)
    actual = {"patch": json.loads(to_json(patch)), "common": common}
    expected = {
        "patch": {
            "__dash_patch_update": "__dash_patch_update",
            "operations": [
                {
                    "operation": "Merge",
                    "location": ["jan"],
                    "params": {"value": {"currency": "USD", "amount": 100}},
                },
                {
                    "operation": "Merge",
                    "location": ["feb"],
                    "params": {"value": {"currency": "USD", "amount": 200}},
                },
            ],
        },
        "common": {"currency": "USD"},
    }
    print("ACTUAL_PRODUCER " + mode + " " + json.dumps(actual, sort_keys=True), flush=True)
    assert actual == expected, (
        f"public producer {mode}: each target must keep its requested amount and "
        "Patch.update must not write kwargs into its source mapping; "
        f"actual={actual!r}; expected={expected!r}"
    )


@pytest.mark.parametrize("mode", MODES)
def test_public_browser(dash_duo, mode):
    app = Dash(__name__)
    app.layout = html.Div(
        [
            html.Button("Apply", id="apply", n_clicks=0),
            dcc.Store(
                id="records",
                data={"jan": {"retained": 1}, "feb": {"retained": 2}},
            ),
            html.Pre(id="records-json"),
            html.Pre(id="common-json"),
        ]
    )
    app.clientside_callback(
        "function(data) { return JSON.stringify(data); }",
        Output("records-json", "children"),
        Input("records", "data"),
    )

    @app.callback(
        Output("records", "data"),
        Output("common-json", "children"),
        Input("apply", "n_clicks"),
        prevent_initial_call=True,
    )
    def apply_patch(_):
        patch, common = make_patch(mode)
        return patch, json.dumps(common, sort_keys=True)

    dash_duo.start_server(app, host="127.0.0.1")
    assert urlparse(dash_duo.driver.current_url).hostname in ("127.0.0.1", "localhost")
    print(
        "ACTUAL_BROWSER_CAPABILITIES "
        + mode
        + " "
        + json.dumps(dash_duo.driver.capabilities, sort_keys=True),
        flush=True,
    )
    dash_duo.find_element("#apply").click()

    def data_received():
        raw_data = dash_duo.find_element("#records-json").text
        raw_common = dash_duo.find_element("#common-json").text
        if not raw_data or not raw_common:
            return False
        data = json.loads(raw_data)
        return all("amount" in data.get(month, {}) for month in ("jan", "feb"))

    try:
        until(data_received, timeout=10, msg=f"{mode}: amount fields never arrived")
    finally:
        print(
            "ACTUAL_BROWSER_RAW "
            + mode
            + " "
            + json.dumps(
                {
                    "data": dash_duo.find_element("#records-json").text,
                    "common": dash_duo.find_element("#common-json").text,
                    "console": dash_duo.get_logs(),
                },
                sort_keys=True,
            ),
            flush=True,
        )
    actual = {
        "data": json.loads(dash_duo.find_element("#records-json").text),
        "common": json.loads(dash_duo.find_element("#common-json").text),
    }
    expected = {
        "data": {
            "jan": {"retained": 1, "currency": "USD", "amount": 100},
            "feb": {"retained": 2, "currency": "USD", "amount": 200},
        },
        "common": {"currency": "USD"},
    }
    print("ACTUAL_BROWSER " + mode + " " + json.dumps(actual, sort_keys=True), flush=True)
    assert actual == expected, (
        f"running Dash browser {mode}: requested amounts must remain100/200, "
        "retained fields must remain1/2, and source mapping must remain unchanged; "
        f"actual={actual!r}; expected={expected!r}"
    )
