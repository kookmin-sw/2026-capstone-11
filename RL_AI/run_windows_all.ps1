cd $env:USERPROFILE
py -u .\start_w.py --log-file .\start.log
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
py -u .\make_balance_w.py --log-file .\make_balance.log
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
py -u .\bias_check_w.py --log-file .\bias_check.log
exit $LASTEXITCODE
