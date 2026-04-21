
namespace Game.Network
{

    public interface ITickable
    {
        public void Tick(int delta);
    }

    public class TickRunner
    {
        private List<ITickable> _tickables;
        private List<ITickable> _registers;
        private List<ITickable> _removed;

        public void RunTick(int delta)
        {
            foreach (var tick in _tickables)
                tick.Tick(delta);
        }
    }
}