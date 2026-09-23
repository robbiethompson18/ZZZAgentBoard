/-
Trusted judge for bounty submissions. Depends on core Lean only.

  judge <pinnedModule> <pinnedDecl>

Loads the pinned module and `Submission` from LEAN_PATH, replays every constant of `Submission` through a
fresh kernel (`Lean.Environment.replay`, the lean4checker core), then checks that `solution` has exactly the
pinned constant's type, or its negation, using no axioms beyond propext / Classical.choice / Quot.sound.

Nothing the submitter wrote is executed here: `importModules` does not run `initialize` blocks unless the
process opts in (the `lean` binary does; this one never does), and the olean's declarations are only trusted
after the kernel has re-checked them. Prints one JSON object on stdout; exit 0 iff ok.
-/
import Lean

open Lean

def okAxioms : List Name := [``propext, ``Classical.choice, ``Quot.sound]

def emit (ok negated : Bool) (axioms : List Name) (error : String) : IO UInt32 := do
  let j := Json.mkObj [("ok", ok), ("negated", negated), ("axioms", toJson (axioms.map toString)), ("error", error)]
  IO.println j.compress
  return if ok then 0 else 1

def fail (msg : String) : IO UInt32 := emit false false [] msg

/-- Axioms reachable from `root` through types and values, read from the kernel environment. -/
partial def axiomsOf (env : Kernel.Environment) (root : Name) : NameSet :=
  go root {} {} |>.1
where
  go (n : Name) (found seen : NameSet) : NameSet × NameSet :=
    if seen.contains n then (found, seen) else
    let seen := seen.insert n
    match env.find? n with
    | some (.axiomInfo _) => (found.insert n, seen)
    | some c =>
      let deps := c.type.getUsedConstants ++ ((c.value? (allowOpaque := true)).map (·.getUsedConstants)).getD #[]
      deps.foldl (fun (f, s) d => go d f s) (found, seen)
    | none => (found, seen)

def main (args : List String) : IO UInt32 := do
  let [pinnedMod, pinnedDecl] := args | fail "usage: judge <pinnedModule> <pinnedDecl>"
  initSearchPath (← findSysroot)
  -- Deserialize the submission's olean on its own (no environment, no imports) for its header and constant list.
  -- Importing it instead would load Mathlib a second time below and double the judge's peak memory (~7GB).
  let (sub, _region) ← readModuleData (← findOLean `Submission)
  if let some c := sub.constants.find? (fun c => c.isUnsafe || c.isPartial || c matches .axiomInfo _) then
    return ← fail s!"unsafe/partial/axiom constant: {c.name}"
  -- Trusted base: the submission's imports plus the pinned module, without the submission itself.
  let base ← importModules (sub.imports.push { module := pinnedMod.toName }) {} (trustLevel := 0)
  let some pinned := base.find? pinnedDecl.toName | fail s!"pinned decl {pinnedDecl} not found"
  let news : Std.HashMap Name ConstantInfo := sub.constants.foldl (fun m c => m.insert c.name c) {}
  let env ← try base.replay news catch e => return ← fail s!"kernel rejected: {e}"
  -- `Environment.ofKernelEnv` (what replay returns) leaves the elaborator-level lookup tables stale; only the
  -- kernel environment reflects what was actually checked, so everything below reads from it.
  let kenv := env.toKernelEnv
  let some sol := kenv.find? `solution | fail "no `solution` declaration"
  unless news.contains `solution do return ← fail "`solution` is not declared in the submission"
  unless sol matches .thmInfo _ | .defnInfo _ do return ← fail "`solution` must be a theorem"
  unless sol.levelParams.isEmpty && pinned.levelParams.isEmpty do return ← fail "universe params not allowed"
  let negated := sol.type == mkNot pinned.type
  unless sol.type == pinned.type || negated do
    return ← fail s!"type mismatch:\n  got  {sol.type}\n  want {pinned.type}"
  let axioms := (axiomsOf kenv `solution).toList
  if let some a := axioms.find? (!okAxioms.contains ·) then
    return ← fail s!"disallowed axiom: {a}"
  emit true negated axioms ""
