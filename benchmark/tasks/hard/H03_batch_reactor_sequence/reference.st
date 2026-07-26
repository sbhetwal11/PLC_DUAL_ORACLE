PROGRAM batch_reactor
VAR_INPUT
    StartBatch : BOOL;
    Level      : INT;  (* 0..100 percent *)
    Temp       : INT;  (* 0..200 *)
    EStop      : BOOL; (* normally-closed: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    FillValve  : BOOL;
    Heater     : BOOL;
    Agitator   : BOOL;
    DrainValve : BOOL;
END_VAR
VAR
    State : INT;
    Tr    : TON;
END_VAR
VAR CONSTANT
    LVL_HIGH : INT := 80;
    LVL_LOW  : INT := 5;
    LIQ_MIN  : INT := 10;
    TEMP_SET : INT := 100;
END_VAR

(* T#3s = 3 scan ticks reaction dwell. *)
Tr(IN := State = 3, PT := T#3s);

IF NOT EStop THEN
    State := 0;
ELSE
    CASE State OF
    0:
        IF StartBatch THEN State := 1; END_IF;
    1:
        IF Level >= LVL_HIGH THEN State := 2; END_IF;
    2:
        IF Temp >= TEMP_SET THEN State := 3; END_IF;
    3:
        IF Tr.Q THEN State := 4; END_IF;
    4:
        IF Level <= LVL_LOW THEN State := 0; END_IF;
    END_CASE;
END_IF;

CASE State OF
0:
    FillValve := FALSE; Heater := FALSE; Agitator := FALSE; DrainValve := FALSE;
1:
    FillValve := TRUE;  Heater := FALSE; Agitator := FALSE; DrainValve := FALSE;
2:
    FillValve := FALSE; Heater := Level >= LIQ_MIN; Agitator := Level >= LIQ_MIN; DrainValve := FALSE;
3:
    FillValve := FALSE; Heater := Level >= LIQ_MIN; Agitator := Level >= LIQ_MIN; DrainValve := FALSE;
4:
    FillValve := FALSE; Heater := FALSE; Agitator := FALSE; DrainValve := TRUE;
END_CASE;

END_PROGRAM
