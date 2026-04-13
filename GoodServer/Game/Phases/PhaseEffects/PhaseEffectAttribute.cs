namespace GoodServer.Game.Phases.PhaseEffects;

[AttributeUsage(AttributeTargets.Class)]
public class PhaseEffectAttribute(Phase phase) : Attribute
{
   public readonly Phase Phase = phase;
}