import copy

import pytest

from mtr_agent.knowledge import Knowledge
from mtr_agent.routing import Router


def test_longest_alias_and_code_switching():
    kb = Knowledge.load()
    assert kb.resolve('由Central去尖沙咀再去Mong Kok') == ['CEN', 'TST', 'MOK']
    assert kb.resolve('香港大學 HKU 去金钟 Admiralty') == ['HKU', 'ADM']
    assert kb.resolve('中環 Central') == ['CEN']
    assert kb.resolve('centralized service') == []


def test_route_has_line_order_transfer_and_evidence():
    route = Router(Knowledge.load()).route('CEN', 'HUH')
    assert route['stations'] == ['CEN', 'ADM', 'EXC', 'HUH']
    assert route['transfers'] == 1
    assert route['minutes'] == 15
    assert route['segments'][1]['line'] == 'EAL'
    assert route['citations']
    assert all(triple['relation'] == 'NEXT_ON_LINE' for triple in route['triples'])


def test_reverse_same_station_and_unknown():
    router = Router(Knowledge.load())
    forward = router.route('HKU', 'HUH')
    reverse = router.route('HUH', 'HKU')
    assert forward['stations'] == list(reversed(reverse['stations']))
    assert router.route('CEN', 'CEN')['minutes'] == 0
    assert router.route('CEN', 'CEN')['transfers'] == 0
    with pytest.raises(ValueError, match='Unknown station'):
        router.route('XXX', 'CEN')
    with pytest.raises(ValueError, match='objective'):
        router.route('CEN', 'ADM', 'cheapest')


def test_optimization_objectives_can_choose_different_routes():
    kb = Knowledge.load()
    data = copy.deepcopy(kb.network.model_dump())
    data['edges'].append({'a': 'CEN', 'b': 'HUH', 'line': 'TWL', 'minutes': 30})
    custom = Knowledge(data, kb.documents)
    router = Router(custom)
    assert router.route('CEN', 'HUH', 'fastest')['transfers'] == 1
    assert router.route('CEN', 'HUH', 'fewest_transfers')['transfers'] == 0


def test_disconnected_and_invalid_network():
    kb = Knowledge.load()
    data = kb.network.model_dump()
    data['edges'] = []
    with pytest.raises(ValueError, match='No route'):
        Router(Knowledge(data, kb.documents)).route('CEN', 'HUH')
    data['edges'] = [{'a': 'CEN', 'b': 'ADM', 'line': 'TWL', 'minutes': -1}]
    with pytest.raises(ValueError):
        Knowledge(data, kb.documents)
    data['edges'] = [{'a': 'CEN', 'b': 'INVALID', 'line': 'TWL', 'minutes': 1}]
    with pytest.raises(ValueError):
        Knowledge(data, kb.documents)
