(* DRAFT - pending expert PLC review. External family-level test candidate. *)
PROGRAM diverter
VAR_INPUT
    DivertCmd   : BOOL;
    AtDivert    : BOOL;
    AtStraight  : BOOL;
    RunConveyor : BOOL;
    Reset       : BOOL;
    EStop       : BOOL;  (* NC: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    GateSolenoid : BOOL;
    ConveyorRun  : BOOL;
    Jam          : BOOL;
END_VAR
VAR
    T1 : TON;
END_VAR

(* Jam-confirm timer: runs while the commanded position is not confirmed,
   the system is healthy, and no jam is yet latched. Called once, top level. *)
T1(IN := ((DivertCmd AND NOT AtDivert) OR (NOT DivertCmd AND NOT AtStraight))
         AND EStop AND NOT Jam,
   PT := T#3s);

(* Latch the jam on timeout; Reset clears it only once the system is healthy
   AND the commanded position is actually confirmed, so a held Reset cannot
   defeat the latch while the gate is still not in position. *)
IF Reset AND EStop AND ((DivertCmd AND AtDivert AND NOT AtStraight)
                        OR (NOT DivertCmd AND AtStraight AND NOT AtDivert)) THEN
    Jam := FALSE;
ELSIF T1.Q THEN
    Jam := TRUE;
END_IF;

(* Gate and conveyor outputs. *)
IF NOT EStop OR Jam THEN
    GateSolenoid := FALSE;
    ConveyorRun := FALSE;
ELSE
    GateSolenoid := DivertCmd;
    ConveyorRun := RunConveyor;
END_IF;

END_PROGRAM
