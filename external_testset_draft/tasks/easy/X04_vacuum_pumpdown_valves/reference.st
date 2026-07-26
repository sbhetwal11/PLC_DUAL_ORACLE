(* DRAFT - pending expert PLC review. External family-level test candidate. *)
PROGRAM vacuum_pumpdown
VAR_INPUT
    Pressure  : INT;   (* mbar, 1000 = atm .. 0 = high vacuum *)
    StartPump : BOOL;
    VentCmd   : BOOL;
    EStop     : BOOL;  (* NC: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    RoughValve : BOOL;
    HiVacValve : BOOL;
    VentValve  : BOOL;
END_VAR
VAR CONSTANT
    P_CROSS : INT := 100;  (* crossover pressure (illustrative; real systems are pump-specific, often 1-10 mbar) *)
END_VAR

(* Priority: isolate on E-stop > vent > staged pump-down.
   Exactly one (or zero) valve open per scan by construction. *)
IF NOT EStop THEN
    RoughValve := FALSE;
    HiVacValve := FALSE;
    VentValve := FALSE;
ELSIF VentCmd THEN
    RoughValve := FALSE;
    HiVacValve := FALSE;
    VentValve := TRUE;
ELSIF StartPump AND Pressure > P_CROSS THEN
    RoughValve := TRUE;
    HiVacValve := FALSE;
    VentValve := FALSE;
ELSIF StartPump AND Pressure <= P_CROSS THEN
    RoughValve := FALSE;
    HiVacValve := TRUE;
    VentValve := FALSE;
ELSE
    RoughValve := FALSE;
    HiVacValve := FALSE;
    VentValve := FALSE;
END_IF;

END_PROGRAM
