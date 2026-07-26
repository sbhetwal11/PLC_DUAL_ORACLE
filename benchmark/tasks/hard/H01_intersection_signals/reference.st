PROGRAM intersection
VAR_OUTPUT
    NS_G : BOOL; NS_Y : BOOL; NS_R : BOOL;
    EW_G : BOOL; EW_Y : BOOL; EW_R : BOOL;
END_VAR
VAR
    State : INT;
    Tg : TON;   (* green timer  *)
    Ty : TON;   (* yellow timer *)
    Ta : TON;   (* all-red timer *)
END_VAR

(* Timers gated by the phases that use each duration. T#Ns = N scan ticks. *)
Tg(IN := (State = 0) OR (State = 3), PT := T#2s);
Ty(IN := (State = 1) OR (State = 4), PT := T#1s);
Ta(IN := (State = 2) OR (State = 5), PT := T#1s);

CASE State OF
0:
    IF Tg.Q THEN State := 1; END_IF;
1:
    IF Ty.Q THEN State := 2; END_IF;
2:
    IF Ta.Q THEN State := 3; END_IF;
3:
    IF Tg.Q THEN State := 4; END_IF;
4:
    IF Ty.Q THEN State := 5; END_IF;
5:
    IF Ta.Q THEN State := 0; END_IF;
END_CASE;

CASE State OF
0:
    NS_G := TRUE;  NS_Y := FALSE; NS_R := FALSE;
    EW_G := FALSE; EW_Y := FALSE; EW_R := TRUE;
1:
    NS_G := FALSE; NS_Y := TRUE;  NS_R := FALSE;
    EW_G := FALSE; EW_Y := FALSE; EW_R := TRUE;
2:
    NS_G := FALSE; NS_Y := FALSE; NS_R := TRUE;
    EW_G := FALSE; EW_Y := FALSE; EW_R := TRUE;
3:
    NS_G := FALSE; NS_Y := FALSE; NS_R := TRUE;
    EW_G := TRUE;  EW_Y := FALSE; EW_R := FALSE;
4:
    NS_G := FALSE; NS_Y := FALSE; NS_R := TRUE;
    EW_G := FALSE; EW_Y := TRUE;  EW_R := FALSE;
5:
    NS_G := FALSE; NS_Y := FALSE; NS_R := TRUE;
    EW_G := FALSE; EW_Y := FALSE; EW_R := TRUE;
END_CASE;

END_PROGRAM
