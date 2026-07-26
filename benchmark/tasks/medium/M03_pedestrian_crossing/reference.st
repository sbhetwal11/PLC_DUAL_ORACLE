PROGRAM ped_crossing
VAR_INPUT
    PedReq : BOOL;
END_VAR
VAR_OUTPUT
    CarGreen  : BOOL;
    CarYellow : BOOL;
    CarRed    : BOOL;
    PedWalk   : BOOL;
END_VAR
VAR
    State : INT;
    T0    : TON;
    T1    : TON;
    T2    : TON;
END_VAR

(* One phase timer per state, gated by the state, all at top level.
   T#Ns = N scan ticks (1 tick = 1 s). *)
T0(IN := State = 0, PT := T#3s);
T1(IN := State = 1, PT := T#2s);
T2(IN := State = 2, PT := T#3s);

(* Phase transitions *)
CASE State OF
0:
    IF T0.Q AND PedReq THEN
        State := 1;
    END_IF;
1:
    IF T1.Q THEN
        State := 2;
    END_IF;
2:
    IF T2.Q THEN
        State := 0;
    END_IF;
END_CASE;

(* One-hot outputs from the (updated) state *)
CASE State OF
0:
    CarGreen := TRUE;  CarYellow := FALSE; CarRed := FALSE; PedWalk := FALSE;
1:
    CarGreen := FALSE; CarYellow := TRUE;  CarRed := FALSE; PedWalk := FALSE;
2:
    CarGreen := FALSE; CarYellow := FALSE; CarRed := TRUE;  PedWalk := TRUE;
END_CASE;

END_PROGRAM
