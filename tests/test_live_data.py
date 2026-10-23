from sentinela_alimentos.live_data import food_class_for, is_food


def test_food_term_filter_handles_accents_and_food_words():
    assert is_food("Aquisição de gêneros alimentícios para merenda")
    assert is_food("Leite integral")
    assert not is_food("Material elétrico")


def test_known_foods_map_to_catmat_subsistence_classes():
    assert food_class_for("arroz") == 8920
    assert food_class_for("tomate") == 8915
