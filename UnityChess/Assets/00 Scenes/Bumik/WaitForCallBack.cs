using UnityEngine;

public class WaitForCallback : CustomYieldInstruction
{
    bool _done = false;
    public override bool keepWaiting => !_done;
    public void Complete() => _done = true;
}