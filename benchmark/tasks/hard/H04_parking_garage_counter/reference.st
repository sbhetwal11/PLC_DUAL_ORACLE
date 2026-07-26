PROGRAM garage
VAR_INPUT
    EntrySensor : BOOL;
    ExitSensor  : BOOL;
    EntryReq    : BOOL;
END_VAR
VAR_OUTPUT
    FullSign         : BOOL;
    EntryBarrierOpen : BOOL;
END_VAR
VAR
    Count     : INT;
    PrevEntry : BOOL;
    PrevExit  : BOOL;
END_VAR
VAR CONSTANT
    CAP : INT := 3;
END_VAR

(* Count up on an entry edge (if not full), down on an exit edge (if not empty). *)
IF EntrySensor AND NOT PrevEntry AND Count < CAP THEN
    Count := Count + 1;
END_IF;
IF ExitSensor AND NOT PrevExit AND Count > 0 THEN
    Count := Count - 1;
END_IF;

PrevEntry := EntrySensor;
PrevExit  := ExitSensor;

FullSign := Count >= CAP;
EntryBarrierOpen := EntryReq AND NOT FullSign;

END_PROGRAM
