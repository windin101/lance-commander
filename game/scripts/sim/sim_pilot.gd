class_name SimPilot
extends RefCounted
## A MechWarrior: skills, specialties and wounds (warrior.cpp).

const DEATH_WOUNDS := 6.0

var name := ""
var gunnery := 50.0
var piloting := 50.0
var wounds := 0.0
var dead := false
var specialties: Dictionary = {}  # specialty name -> true


static func from_fit(fit: Dictionary) -> SimPilot:
	var p := SimPilot.new()
	var general: Dictionary = fit.get("General", {})
	p.name = general.get("Callsign", general.get("Name", ""))
	var skills: Dictionary = fit.get("Skills", {})
	p.gunnery = skills.get("Gunnery", 50)
	p.piloting = skills.get("Piloting", 50)
	for key in fit.get("SpecialtySkills", {}):
		if int(fit["SpecialtySkills"][key]) == 1:
			p.specialties[key] = true
	return p


static func make(gunnery_skill: float, piloting_skill: float, specialty_names: Array = []) -> SimPilot:
	var p := SimPilot.new()
	p.gunnery = gunnery_skill
	p.piloting = piloting_skill
	for s in specialty_names:
		p.specialties[s] = true
	return p


func has(specialty: String) -> bool:
	return specialties.has(specialty)


## Returns true if this injury killed the pilot (MechWarrior::injure).
func injure(amount: float) -> bool:
	if dead:
		return false
	wounds += amount
	if wounds >= DEATH_WOUNDS:
		dead = true
		return true
	return false
