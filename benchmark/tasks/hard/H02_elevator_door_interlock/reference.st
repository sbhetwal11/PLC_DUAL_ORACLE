PROGRAM elevator
VAR_INPUT
    CallUp     : BOOL;
    CallDown   : BOOL;
    DoorClosed : BOOL;
    AtTop      : BOOL;
    AtBottom   : BOOL;
END_VAR
VAR_OUTPUT
    MotorUp   : BOOL;
    MotorDown : BOOL;
END_VAR
VAR
    State : INT;
END_VAR

(* Travel direction state machine *)
CASE State OF
0:
    IF CallUp THEN State := 1; END_IF;
1:
    IF AtTop THEN State := 2; END_IF;
2:
    IF CallDown THEN State := 3; END_IF;
3:
    IF AtBottom THEN State := 0; END_IF;
END_CASE;

(* Motor outputs gated by the door interlock and end limits (safety by construction) *)
CASE State OF
0:
    MotorUp := FALSE; MotorDown := FALSE;
1:
    MotorUp := DoorClosed AND NOT AtTop;    MotorDown := FALSE;
2:
    MotorUp := FALSE; MotorDown := FALSE;
3:
    MotorUp := FALSE; MotorDown := DoorClosed AND NOT AtBottom;
END_CASE;

END_PROGRAM
