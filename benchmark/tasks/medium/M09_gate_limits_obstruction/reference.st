PROGRAM gate
VAR_INPUT
    OpenCmd     : BOOL;
    CloseCmd    : BOOL;
    OpenLimit   : BOOL;
    CloseLimit  : BOOL;
    Obstruction : BOOL;
END_VAR
VAR_OUTPUT
    MotorOpen  : BOOL;
    MotorClose : BOOL;
END_VAR
VAR
    State : INT;
END_VAR

(* Obstruction immediately stops a closing gate. *)
IF Obstruction AND State = 2 THEN
    State := 0;
END_IF;

CASE State OF
0:
    IF OpenCmd AND NOT OpenLimit THEN
        State := 1;
    ELSIF CloseCmd AND NOT CloseLimit AND NOT Obstruction THEN
        State := 2;
    END_IF;
1:
    IF OpenLimit THEN
        State := 0;
    END_IF;
2:
    IF CloseLimit THEN
        State := 0;
    END_IF;
END_CASE;

CASE State OF
0:
    MotorOpen := FALSE; MotorClose := FALSE;
1:
    MotorOpen := TRUE;  MotorClose := FALSE;
2:
    MotorOpen := FALSE; MotorClose := TRUE;
END_CASE;

END_PROGRAM
