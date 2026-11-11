"""Cache semeado (C3-mf): copia entradas sem sobrescrever e as entradas copiadas sao acertos de cache."""
from cache import DiskCache, make_key, seed_cache


def test_seed_copies_new_entries_and_never_overwrites(tmp_path):
    src, dst = tmp_path / "seed", tmp_path / "work"
    k1, k2 = make_key(a=1), make_key(a=2)
    DiskCache(src).put(k1, {"v": "da semente 1"})
    DiskCache(src).put(k2, {"v": "da semente 2"})
    DiskCache(dst).put(k2, {"v": "ja existia"})
    assert seed_cache(src, dst) == 1
    cache = DiskCache(dst)
    assert cache.get(k1) == {"v": "da semente 1"}
    assert cache.get(k2) == {"v": "ja existia"}                      # nao sobrescreve
    assert seed_cache(src, dst) == 0                                  # idempotente


def test_seed_of_missing_source_dir_copies_nothing(tmp_path):
    assert seed_cache(tmp_path / "nao_existe", tmp_path / "work") == 0
