(* DRAFT - pending expert PLC review. External family-level test candidate. *)
PROGRAM cooling_tower
VAR_INPUT
    WaterTemp : INT;   (* deg C, 0..120 *)
    Enable    : BOOL;
    EStop     : BOOL;  (* normally-closed: TRUE = healthy, FALSE = activated *)
END_VAR
VAR_OUTPUT
    Fan1 : BOOL;  (* lead *)
    Fan2 : BOOL;  (* lag  *)
END_VAR
VAR CONSTANT
    T_ON1 : INT := 25;  (* lead stage point *)
    T_ON2 : INT := 32;  (* lag  stage point *)
END_VAR

(* Monotonic staging: pure rising thresholds, no hysteresis.
   T_ON2 > T_ON1 guarantees Fan2 -> Fan1. *)
IF NOT EStop OR NOT Enable THEN
    Fan1 := FALSE;
    Fan2 := FALSE;
ELSE
    Fan1 := WaterTemp >= T_ON1;
    Fan2 := WaterTemp >= T_ON2;
END_IF;

END_PROGRAM
