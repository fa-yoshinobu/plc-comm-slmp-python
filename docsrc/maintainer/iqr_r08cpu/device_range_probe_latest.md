# Device Range Probe Report

- Date: 2026-03-13 17:24:08
- Host: 192.168.250.101
- Port: 1025
- Transport: tcp
- Series: iqr
- Target: network=0x00, station=0xFF, module_io=0x03FF, multidrop=0x00
- Specs: 31
- Include writeback: True
- Include out-of-range write: True
- Summary: PASS=133, WARN=6, NG=0, SKIP=16

| Item | Status | Detail |
|---|---|---|
| X in-range read | PASS | device=X2FFF, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| X crossing read | PASS | device=X2FFF, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| X out-of-range read | PASS | device=X3000, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| X in-range same-value writeback | PASS | device=X2FFF, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| X out-of-range write | PASS | device=X3000, expected=end_code!=0x0000, observed=end_code=0x4031, values=[False] |
| Y in-range read | PASS | device=Y2FFF, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| Y crossing read | PASS | device=Y2FFF, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| Y out-of-range read | PASS | device=Y3000, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| Y in-range same-value writeback | PASS | device=Y2FFF, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| Y out-of-range write | PASS | device=Y3000, expected=end_code!=0x0000, observed=end_code=0x4031, values=[False] |
| M in-range read | PASS | device=M12287, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| M crossing read | PASS | device=M12287, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| M out-of-range read | PASS | device=M12288, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| M in-range same-value writeback | PASS | device=M12287, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| M out-of-range write | PASS | device=M12288, expected=end_code!=0x0000, observed=end_code=0x4031, values=[False] |
| B in-range read | PASS | device=B1FFF, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| B crossing read | PASS | device=B1FFF, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| B out-of-range read | PASS | device=B2000, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| B in-range same-value writeback | PASS | device=B1FFF, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| B out-of-range write | PASS | device=B2000, expected=end_code!=0x0000, observed=end_code=0x4031, values=[False] |
| SB in-range read | PASS | device=SB7FF, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| SB crossing read | PASS | device=SB7FF, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| SB out-of-range read | PASS | device=SB800, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| SB in-range same-value writeback | PASS | device=SB7FF, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| SB out-of-range write | PASS | device=SB800, expected=end_code!=0x0000, observed=end_code=0x4031, values=[False] |
| F in-range read | PASS | device=F2047, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| F crossing read | PASS | device=F2047, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| F out-of-range read | PASS | device=F2048, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| F in-range same-value writeback | PASS | device=F2047, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| F out-of-range write | PASS | device=F2048, expected=end_code!=0x0000, observed=end_code=0x4031, values=[False] |
| V in-range read | PASS | device=V2047, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| V crossing read | PASS | device=V2047, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| V out-of-range read | PASS | device=V2048, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| V in-range same-value writeback | PASS | device=V2047, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| V out-of-range write | PASS | device=V2048, expected=end_code!=0x0000, observed=end_code=0x4031, values=[False] |
| S in-range read | PASS | device=S1023, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| S crossing read | PASS | device=S1023, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| S out-of-range read | PASS | device=S1024, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| S in-range same-value writeback | WARN | device=S1023, expected=end_code=0x0000, observed=end_code=0x4030, values=[False] |
| S out-of-range write | PASS | device=S1024, expected=end_code!=0x0000, observed=end_code=0x4031, values=[False] |
| TS in-range read | PASS | device=TS1023, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| TS crossing read | PASS | device=TS1023, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| TS out-of-range read | PASS | device=TS1024, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| TS in-range same-value writeback | PASS | device=TS1023, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| TS out-of-range write | PASS | device=TS1024, expected=end_code!=0x0000, observed=end_code=0x4031, values=[False] |
| TC in-range read | PASS | device=TC1023, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| TC crossing read | PASS | device=TC1023, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| TC out-of-range read | PASS | device=TC1024, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| TC in-range same-value writeback | PASS | device=TC1023, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| TC out-of-range write | PASS | device=TC1024, expected=end_code!=0x0000, observed=end_code=0x4031, values=[False] |
| TN in-range read | PASS | device=TN1023, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[0] |
| TN crossing read | PASS | device=TN1023, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| TN out-of-range read | PASS | device=TN1024, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| TN in-range same-value writeback | PASS | device=TN1023, expected=end_code=0x0000, observed=end_code=0x0000, values=[0] |
| TN out-of-range write | PASS | device=TN1024, expected=end_code!=0x0000, observed=end_code=0x4031, values=[0] |
| LTS in-range read | WARN | device=LTS1023, points=1, expected=end_code=0x0000, observed=end_code=0x4030, note=known direct-path issue on validated iQ-R target |
| LTS crossing read | SKIP | baseline in-range read failed with end_code=0x4030; boundary behavior is not isolated |
| LTS out-of-range read | SKIP | baseline in-range read failed with end_code=0x4030; boundary behavior is not isolated |
| LTS in-range same-value writeback | SKIP | baseline in-range read failed with end_code=0x4030; boundary behavior is not isolated |
| LTS out-of-range write | SKIP | baseline in-range read failed with end_code=0x4030; boundary behavior is not isolated |
| LTC in-range read | WARN | device=LTC1023, points=1, expected=end_code=0x0000, observed=end_code=0x4030, note=known direct-path issue on validated iQ-R target |
| LTC crossing read | SKIP | baseline in-range read failed with end_code=0x4030; boundary behavior is not isolated |
| LTC out-of-range read | SKIP | baseline in-range read failed with end_code=0x4030; boundary behavior is not isolated |
| LTC in-range same-value writeback | SKIP | baseline in-range read failed with end_code=0x4030; boundary behavior is not isolated |
| LTC out-of-range write | SKIP | baseline in-range read failed with end_code=0x4030; boundary behavior is not isolated |
| LTN in-range read | PASS | device=LTN1023, points=4, expected=end_code=0x0000, observed=end_code=0x0000, values=[0, 0, 0, 0] |
| LTN crossing read | PASS | device=LTN1023, points=5, expected=end_code!=0x0000, observed=end_code=0x4031 |
| LTN out-of-range read | PASS | device=LTN1024, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| LTN in-range same-value writeback | PASS | device=LTN1023, expected=end_code=0x0000, observed=end_code=0x0000, values=[0, 0, 0, 0] |
| LTN out-of-range write | PASS | device=LTN1024, expected=end_code!=0x0000, observed=end_code=0xC051, values=[0] |
| STS in-range read | PASS | device=STS1023, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| STS crossing read | PASS | device=STS1023, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| STS out-of-range read | PASS | device=STS1024, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| STS in-range same-value writeback | PASS | device=STS1023, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| STS out-of-range write | PASS | device=STS1024, expected=end_code!=0x0000, observed=end_code=0x4031, values=[False] |
| STC in-range read | PASS | device=STC1023, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| STC crossing read | PASS | device=STC1023, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| STC out-of-range read | PASS | device=STC1024, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| STC in-range same-value writeback | PASS | device=STC1023, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| STC out-of-range write | PASS | device=STC1024, expected=end_code!=0x0000, observed=end_code=0x4031, values=[False] |
| STN in-range read | PASS | device=STN1023, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[0] |
| STN crossing read | PASS | device=STN1023, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| STN out-of-range read | PASS | device=STN1024, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| STN in-range same-value writeback | PASS | device=STN1023, expected=end_code=0x0000, observed=end_code=0x0000, values=[0] |
| STN out-of-range write | PASS | device=STN1024, expected=end_code!=0x0000, observed=end_code=0x4031, values=[0] |
| LSTS in-range read | WARN | device=LSTS1023, points=1, expected=end_code=0x0000, observed=end_code=0x4030, note=known direct-path issue on validated iQ-R target |
| LSTS crossing read | SKIP | baseline in-range read failed with end_code=0x4030; boundary behavior is not isolated |
| LSTS out-of-range read | SKIP | baseline in-range read failed with end_code=0x4030; boundary behavior is not isolated |
| LSTS in-range same-value writeback | SKIP | baseline in-range read failed with end_code=0x4030; boundary behavior is not isolated |
| LSTS out-of-range write | SKIP | baseline in-range read failed with end_code=0x4030; boundary behavior is not isolated |
| LSTC in-range read | WARN | device=LSTC1023, points=1, expected=end_code=0x0000, observed=end_code=0x4030, note=known direct-path issue on validated iQ-R target |
| LSTC crossing read | SKIP | baseline in-range read failed with end_code=0x4030; boundary behavior is not isolated |
| LSTC out-of-range read | SKIP | baseline in-range read failed with end_code=0x4030; boundary behavior is not isolated |
| LSTC in-range same-value writeback | SKIP | baseline in-range read failed with end_code=0x4030; boundary behavior is not isolated |
| LSTC out-of-range write | SKIP | baseline in-range read failed with end_code=0x4030; boundary behavior is not isolated |
| LSTN in-range read | PASS | device=LSTN1023, points=4, expected=end_code=0x0000, observed=end_code=0x0000, values=[0, 0, 0, 0] |
| LSTN crossing read | PASS | device=LSTN1023, points=5, expected=end_code!=0x0000, observed=end_code=0x4031 |
| LSTN out-of-range read | PASS | device=LSTN1024, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| LSTN in-range same-value writeback | PASS | device=LSTN1023, expected=end_code=0x0000, observed=end_code=0x0000, values=[0, 0, 0, 0] |
| LSTN out-of-range write | PASS | device=LSTN1024, expected=end_code!=0x0000, observed=end_code=0xC051, values=[0] |
| CS in-range read | PASS | device=CS511, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| CS crossing read | PASS | device=CS511, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| CS out-of-range read | PASS | device=CS512, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| CS in-range same-value writeback | PASS | device=CS511, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| CS out-of-range write | PASS | device=CS512, expected=end_code!=0x0000, observed=end_code=0x4031, values=[False] |
| CC in-range read | PASS | device=CC511, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| CC crossing read | PASS | device=CC511, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| CC out-of-range read | PASS | device=CC512, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| CC in-range same-value writeback | PASS | device=CC511, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| CC out-of-range write | PASS | device=CC512, expected=end_code!=0x0000, observed=end_code=0x4031, values=[False] |
| CN in-range read | PASS | device=CN511, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[0] |
| CN crossing read | PASS | device=CN511, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| CN out-of-range read | PASS | device=CN512, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| CN in-range same-value writeback | PASS | device=CN511, expected=end_code=0x0000, observed=end_code=0x0000, values=[0] |
| CN out-of-range write | PASS | device=CN512, expected=end_code!=0x0000, observed=end_code=0x4031, values=[0] |
| LCS in-range read | PASS | device=LCS511, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| LCS crossing read | PASS | device=LCS511, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| LCS out-of-range read | PASS | device=LCS512, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| LCS in-range same-value writeback | PASS | device=LCS511, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| LCS out-of-range write | PASS | device=LCS512, expected=end_code!=0x0000, observed=end_code=0x4031, values=[False] |
| LCC in-range read | PASS | device=LCC511, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| LCC crossing read | PASS | device=LCC511, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| LCC out-of-range read | PASS | device=LCC512, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| LCC in-range same-value writeback | PASS | device=LCC511, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| LCC out-of-range write | PASS | device=LCC512, expected=end_code!=0x0000, observed=end_code=0x4031, values=[False] |
| LCN in-range read | PASS | device=LCN511, points=2, expected=end_code=0x0000, observed=end_code=0x0000, values=[0, 0] |
| LCN crossing read | PASS | device=LCN511, points=3, expected=end_code!=0x0000, observed=end_code=0x4031 |
| LCN out-of-range read | PASS | device=LCN512, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| LCN in-range same-value writeback | PASS | device=LCN511, expected=end_code=0x0000, observed=end_code=0x0000, values=[0, 0] |
| LCN out-of-range write | PASS | device=LCN512, expected=end_code!=0x0000, observed=end_code=0xC051, values=[0] |
| D in-range read | PASS | device=D10239, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[0] |
| D crossing read | PASS | device=D10239, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| D out-of-range read | PASS | device=D10240, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| D in-range same-value writeback | PASS | device=D10239, expected=end_code=0x0000, observed=end_code=0x0000, values=[0] |
| D out-of-range write | PASS | device=D10240, expected=end_code!=0x0000, observed=end_code=0x4031, values=[0] |
| W in-range read | PASS | device=W1FFF, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[0] |
| W crossing read | PASS | device=W1FFF, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| W out-of-range read | PASS | device=W2000, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| W in-range same-value writeback | PASS | device=W1FFF, expected=end_code=0x0000, observed=end_code=0x0000, values=[0] |
| W out-of-range write | PASS | device=W2000, expected=end_code!=0x0000, observed=end_code=0x4031, values=[0] |
| SW in-range read | PASS | device=SW7FF, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[0] |
| SW crossing read | PASS | device=SW7FF, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| SW out-of-range read | PASS | device=SW800, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| SW in-range same-value writeback | PASS | device=SW7FF, expected=end_code=0x0000, observed=end_code=0x0000, values=[0] |
| SW out-of-range write | PASS | device=SW800, expected=end_code!=0x0000, observed=end_code=0x4031, values=[0] |
| L in-range read | PASS | device=L8191, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| L crossing read | PASS | device=L8191, points=2, expected=end_code!=0x0000, observed=end_code=0x4031 |
| L out-of-range read | PASS | device=L8192, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| L in-range same-value writeback | PASS | device=L8191, expected=end_code=0x0000, observed=end_code=0x0000, values=[False] |
| L out-of-range write | PASS | device=L8192, expected=end_code!=0x0000, observed=end_code=0x4031, values=[False] |
| ZR in-range read | PASS | device=ZR163839, points=1, expected=end_code=0x0000, observed=end_code=0x0000, values=[0] |
| ZR crossing read | WARN | device=ZR163839, points=2, expected=end_code!=0x0000, observed=end_code=0x0000, values=[0, 0] |
| ZR out-of-range read | PASS | device=ZR163840, points=1, expected=end_code!=0x0000, observed=end_code=0x4031 |
| ZR in-range same-value writeback | PASS | device=ZR163839, expected=end_code=0x0000, observed=end_code=0x0000, values=[0] |
| ZR out-of-range write | PASS | device=ZR163840, expected=end_code!=0x0000, observed=end_code=0x4031, values=[0] |
