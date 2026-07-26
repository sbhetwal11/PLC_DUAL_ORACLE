PROGRAM pump_alt
VAR_INPUT
    Demand : BOOL;
    EStop  : BOOL; (* normally-closed: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    Pump1 : BOOL;
    Pump2 : BOOL;
END_VAR
VAR
    Lead       : INT;
    PrevDemand : BOOL;
END_VAR

(* Outputs: run the current lead pump while demand is present and healthy. *)
IF NOT EStop THEN
    Pump1 := FALSE;
    Pump2 := FALSE;
ELSIF Demand THEN
    IF Lead = 0 THEN
        Pump1 := TRUE;  Pump2 := FALSE;
    ELSE
        Pump1 := FALSE; Pump2 := TRUE;
    END_IF;
ELSE
    Pump1 := FALSE;
    Pump2 := FALSE;
END_IF;

(* Alternate the lead role on the falling edge of demand. *)
IF PrevDemand AND NOT Demand THEN
    IF Lead = 0 THEN
        Lead := 1;
    ELSE
        Lead := 0;
    END_IF;
END_IF;

PrevDemand := Demand;

END_PROGRAM
