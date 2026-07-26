PROGRAM airlock
VAR_INPUT
    OpenA_Cmd : BOOL;
    OpenB_Cmd : BOOL;
END_VAR
VAR_OUTPUT
    DoorA : BOOL;
    DoorB : BOOL;
END_VAR

(* Door A may open only if door B is currently closed. *)
IF OpenA_Cmd AND NOT DoorB THEN
    DoorA := TRUE;
ELSE
    DoorA := FALSE;
END_IF;

(* Door B may open only if door A is closed (uses A's freshly-updated value,
   so A has priority and the two can never be open together). *)
IF OpenB_Cmd AND NOT DoorA THEN
    DoorB := TRUE;
ELSE
    DoorB := FALSE;
END_IF;

END_PROGRAM
