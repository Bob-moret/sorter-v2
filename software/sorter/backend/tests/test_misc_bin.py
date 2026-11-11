"""MISC_BIN: misc pieces go to one bin instead of through the open doors, for a
machine whose doors cannot open yet. Unset, misc passes through as before."""

from __future__ import annotations

import queue
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from subsystems.distribution.chute import BinAddress
from subsystems.distribution.positioning import Positioning
from subsystems.shared_variables import SharedVariables
from sorting_profile import MISC_CATEGORY


class _Logger:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def info(self, *a, **k) -> None:
        pass

    def debug(self, *a, **k) -> None:
        pass

    def warning(self, msg: str, *a, **k) -> None:
        self.warnings.append(msg)

    def error(self, *a, **k) -> None:
        pass


def _bin(*category_ids: str) -> SimpleNamespace:
    return SimpleNamespace(category_ids=list(category_ids), not_in_inventory=False)


def _mkPositioning(sections: list[list[SimpleNamespace]]) -> Positioning:
    gc = SimpleNamespace(
        logger=_Logger(),
        runtime_stats=SimpleNamespace(observeStateTransition=lambda *a, **k: None),
        disable_servos=False,
    )
    layout = SimpleNamespace(
        layers=[
            SimpleNamespace(
                enabled=True,
                max_dimension_mm=None,
                max_pieces_per_bin=None,
                sections=[SimpleNamespace(enabled=True, bins=bins) for bins in sections],
            )
        ]
    )
    chute = SimpleNamespace(
        moveToBin=lambda address: 100,
        isBinReachable=lambda address: True,
        stepper=SimpleNamespace(stopped=True),
        checking=False,
        positionCheckDue=lambda: False,
    )
    sorting_profile = SimpleNamespace(
        getCategoryIdForPart=lambda part_id, color_id: "cat_a",
        highValueCategoryId=lambda price: None,
    )
    positioning = Positioning(
        SimpleNamespace(servos=[SimpleNamespace(available=True)]),  # type: ignore[arg-type]
        gc,  # type: ignore[arg-type]
        SharedVariables(),
        chute,  # type: ignore[arg-type]
        layout,  # type: ignore[arg-type]
        sorting_profile,  # type: ignore[arg-type]
        queue.Queue(),
    )
    positioning._isLayerUsable = lambda layer_index: True  # type: ignore[method-assign]
    return positioning


@pytest.fixture(autouse=True)
def _noDatabase():
    with patch("bin_contents.get_current_bin_piece_counts", return_value={}), patch(
        "subsystems.distribution.positioning._persistBinCategories", lambda layout: None
    ):
        yield


def _sixByThree() -> list[list[SimpleNamespace]]:
    return [[_bin("taken") for _ in range(3)] for _ in range(6)]


def test_misc_goes_to_the_bin_misc_bin_names(monkeypatch) -> None:
    monkeypatch.setenv("MISC_BIN", "1,18")
    positioning = _mkPositioning(_sixByThree())
    assert positioning._findOrAssignBinForCategory(MISC_CATEGORY) == (BinAddress(0, 5, 2), False)


def test_without_misc_bin_misc_still_passes_through(monkeypatch) -> None:
    monkeypatch.delenv("MISC_BIN", raising=False)
    positioning = _mkPositioning(_sixByThree())
    assert positioning._findOrAssignBinForCategory(MISC_CATEGORY) == (None, False)


def test_a_new_category_never_claims_the_misc_bin(monkeypatch) -> None:
    monkeypatch.setenv("MISC_BIN", "1,1")
    sections = [[_bin(), _bin()], [_bin("taken")]]
    positioning = _mkPositioning(sections)
    address, assigned = positioning._findOrAssignBinForCategory("cat_new")
    assert (address, assigned) == (BinAddress(0, 0, 1), True)
    assert sections[0][0].category_ids == []


def test_a_bin_the_layout_does_not_have_is_said_and_ignored(monkeypatch) -> None:
    monkeypatch.setenv("MISC_BIN", "1,99")
    positioning = _mkPositioning(_sixByThree())
    assert positioning._findOrAssignBinForCategory(MISC_CATEGORY) == (None, False)
    assert any("MISC_BIN" in w for w in positioning.gc.logger.warnings)


@pytest.mark.parametrize("raw", ["18", "a,b", "0,3", "1,2,3"])
def test_an_unreadable_setting_is_ignored(monkeypatch, raw: str) -> None:
    monkeypatch.setenv("MISC_BIN", raw)
    positioning = _mkPositioning(_sixByThree())
    assert positioning._findOrAssignBinForCategory(MISC_CATEGORY) == (None, False)
