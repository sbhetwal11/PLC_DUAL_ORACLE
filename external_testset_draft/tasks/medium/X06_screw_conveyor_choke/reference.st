(* DRAFT - pending expert PLC review. External family-level test candidate. *)
PROGRAM screw_conveyor
VAR_INPUT
    StartCmd      : BOOL;
    DownstreamRun : BOOL;
    ChokeSwitch   : BOOL;  (* TRUE = trough blocked *)
    Reset         : BOOL;
    EStop         : BOOL;  (* NC: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    ScrewMotor : BOOL;
    ChokeTrip  : BOOL;
END_VAR
VAR
    T1 : TON;
END_VAR

(* Choke-confirm timer: counts while the screw is permitted to run and a
   choke is present, and no trip is yet latched. Called once, top level. *)
T1(IN := StartCmd AND DownstreamRun AND EStop AND ChokeSwitch AND NOT ChokeTrip,
   PT := T#2s);

(* Latch trip on confirmed choke; Reset clears when healthy, the choke has
   cleared, AND the start command is not held - the operator must cycle StartCmd
   off to acknowledge, so the screw cannot restart straight through a reset. *)
IF Reset AND EStop AND NOT ChokeSwitch AND NOT StartCmd THEN
    ChokeTrip := FALSE;
ELSIF T1.Q THEN
    ChokeTrip := TRUE;
END_IF;

(* Downstream-first permissive + trip lockout. *)
IF NOT EStop OR ChokeTrip OR NOT DownstreamRun THEN
    ScrewMotor := FALSE;
ELSIF StartCmd THEN
    ScrewMotor := TRUE;
ELSE
    ScrewMotor := FALSE;
END_IF;

END_PROGRAM
