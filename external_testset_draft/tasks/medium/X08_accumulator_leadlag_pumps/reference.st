(* DRAFT - pending expert PLC review. External family-level test candidate. *)
PROGRAM accumulator
VAR_INPUT
    Pressure : INT;   (* bar, 0..300 *)
    Enable   : BOOL;
    EStop    : BOOL;  (* NC: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    LeadPump    : BOOL;
    LagPump     : BOOL;
    ReliefValve : BOOL;
END_VAR
VAR CONSTANT
    P_LEAD : INT := 200;
    P_LAG  : INT := 150;
    P_MAX  : INT := 280;
END_VAR

(* Relief is a pressure-driven safety device (independent of E-stop). *)
ReliefValve := Pressure >= P_MAX;

(* Fixed-role lead/lag staging; both inhibited at over-pressure.
   P_LAG < P_LEAD guarantees LagPump -> LeadPump. *)
IF NOT EStop OR NOT Enable OR Pressure >= P_MAX THEN
    LeadPump := FALSE;
    LagPump := FALSE;
ELSE
    LeadPump := Pressure < P_LEAD;
    LagPump := Pressure < P_LAG;
END_IF;

END_PROGRAM
