
namespace Game.Network
{
    public interface ITransferConfigurator
    {
        public abstract string GetHostIPAddress();
        public abstract string GetHostPortNumber();
        public abstract string GetClientIPAddress();
        public abstract string GetClientPortNumber();
    };

}