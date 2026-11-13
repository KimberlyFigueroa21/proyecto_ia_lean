import Mathlib
open Lean Meta Elab

set_option maxHeartbeats 0

/-- Prefijos de módulo que se indexan: lo que usan los problemas de miniF2F (aritmética, álgebra
elemental, teoría de números, funciones especiales, conteo) más el núcleo de Lean y Batteries. -/
def keepPrefixes : List String :=
  ["Init.Data.Nat", "Init.Data.Int", "Init.Data.List", "Init.Data.Fin", "Init.Core", "Init.Prelude",
   "Init.SimpLemmas", "Init.Data.Rat", "Init.Data.Order", "Init.Order",
   "Std.Data.Nat", "Std.Data.Int", "Batteries.Data.Nat", "Batteries.Data.Int", "Batteries.Data.List",
   "Mathlib.Algebra", "Mathlib.NumberTheory", "Mathlib.Data.Nat", "Mathlib.Data.Int", "Mathlib.Data.Real",
   "Mathlib.Data.Rat", "Mathlib.Data.Complex", "Mathlib.Data.Finset", "Mathlib.Data.Fintype",
   "Mathlib.Data.ZMod", "Mathlib.Data.List", "Mathlib.Data.Set", "Mathlib.Order",
   "Mathlib.Analysis.SpecialFunctions", "Mathlib.Analysis.MeanInequalities", "Mathlib.Analysis.Real",
   "Mathlib.Combinatorics", "Mathlib.Tactic"]

def keepModule (m : Name) : Bool :=
  let s := m.toString
  keepPrefixes.any (fun p => s.startsWith p)

def cleanText (s : String) : String :=
  s.map fun c => if c.isWhitespace then ' ' else c

def dumpPath : String := "/workspace/proyecto_ia_lean/rag_data/decls_lean.jsonl"

#eval show MetaM Unit from do
  let env ← getEnv
  let consts := env.constants.fold (fun acc n ci => acc.push (n, ci)) (#[] : Array (Name × ConstantInfo))
  let h ← IO.FS.Handle.mk dumpPath IO.FS.Mode.write
  let mut kept := 0
  let mut seen := 0
  for (name, ci) in consts do
    seen := seen + 1
    unless ci matches .thmInfo _ do continue
    if name.isInternal || isPrivateName name then continue
    let some idx := env.getModuleIdxFor? name | continue
    let mod := env.header.moduleNames[idx.toNat]!
    unless keepModule mod do continue
    let ty ← try ppExpr ci.type catch _ => continue
    let doc := (← findDocString? env name).getD ""
    let sig := cleanText s!"theorem {name} : {ty.pretty 10000}"
    let rec' := Json.mkObj [("name", Json.str name.toString), ("signature", Json.str sig),
                            ("docstring", Json.str (cleanText doc)), ("file", Json.str mod.toString)]
    h.putStrLn rec'.compress
    kept := kept + 1
  h.flush
  logInfo m!"constantes vistas: {seen}; teoremas guardados: {kept}"
