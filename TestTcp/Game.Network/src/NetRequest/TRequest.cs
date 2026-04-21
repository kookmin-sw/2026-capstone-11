
namespace Game.Network.Service
{
    public interface IRequest<TMessage, TResult>
    {
        void Request(TMessage msg, Action<TResult> succ, Action<string> fail);
    }

    public interface IRequestHandler<TMessage, TResult>
    {
        TResult Handle(ConnId connId, TMessage msg);
    }

}