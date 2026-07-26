PROGRAM conveyor3
VAR_INPUT
    StartPB : BOOL;
    StopPB  : BOOL;
    EStop   : BOOL; (* normally-closed: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    C1 : BOOL;
    C2 : BOOL;
    C3 : BOOL;
END_VAR
VAR
    State : INT;
    T1 : TON;   (* C3 -> +C2 delay *)
    T2 : TON;   (* +C2 -> +C1 delay *)
END_VAR

(* T#2s = 2 scan ticks per stage. *)
T1(IN := State = 1, PT := T#2s);
T2(IN := State = 2, PT := T#2s);

IF (NOT EStop) OR StopPB THEN
    State := 0;
ELSE
    CASE State OF
    0:
        IF StartPB THEN State := 1; END_IF;
    1:
        IF T1.Q THEN State := 2; END_IF;
    2:
        IF T2.Q THEN State := 3; END_IF;
    END_CASE;
END_IF;

CASE State OF
0:
    C1 := FALSE; C2 := FALSE; C3 := FALSE;
1:
    C1 := FALSE; C2 := FALSE; C3 := TRUE;
2:
    C1 := FALSE; C2 := TRUE;  C3 := TRUE;
3:
    C1 := TRUE;  C2 := TRUE;  C3 := TRUE;
END_CASE;

END_PROGRAM
