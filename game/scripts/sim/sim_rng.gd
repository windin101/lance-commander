class_name SimRng
extends RefCounted
## Seeded RNG for the simulation. roll(n) matches the original's RandomNumber(n):
## an integer in [0, n-1]. Tests can queue exact values with force().

var _rng := RandomNumberGenerator.new()
var _forced: Array[int] = []


func _init(seed_value: int = 0) -> void:
	_rng.seed = seed_value


func roll(n: int) -> int:
	if not _forced.is_empty():
		return _forced.pop_front()
	if n <= 0:
		return 0
	return _rng.randi_range(0, n - 1)


## Queue values that the next roll() calls return, in order (ignores n).
func force(values: Array) -> void:
	for v in values:
		_forced.append(int(v))


func forced_remaining() -> int:
	return _forced.size()
