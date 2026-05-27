
using Game.Network.Protocol;

namespace Game.Network
{
    // public abstract class AuthModule : ServiceModule
    // {
    //     public int HandlerId => NetEventHandlerId.Constant.Auth;

    //     protected abstract AuthenticateInfo Authenticate(ConnectionInfo info);
        
    //     public AuthModule(INetAPI net, ServiceContext context) : base(net, context) {}

    //     public void OnQuery(string ConnId, int queryNum, byte[] raw)
    //     {
    //         // Accept Hello Info.
    //         var connInfo = ConnectionInfo.Deserialize(raw);

    //         if (connInfo == null)
    //         {
    //             Log.WriteLog("[Service]: Hello Packet Failure");
    //             Net.Disconnect(ConnId);
    //             return;
    //         }

    //         //var authInfo = _auth.Authenticate(ConnId, connInfo);

    //         if (!authInfo.IsAuth)
    //         {
    //             Log.WriteLog($"[Service]: Authenticate Fail. Reason: {authInfo.FailMsg}");
    //             Net.Disconnect(ConnId);
    //             return;
    //         }

    //         // Send Service Key
    //         Net.Send(HandlerId, queryNum, ConnId, Array.Empty<byte>());
    //     }


    //     private void SendRejectedMSG(string ConnId, int queryNum)
    //     {
    //         // Rejected MSG
    //         Net.Send(HandlerId, queryNum, ConnId, Array.Empty<byte>());
    //     }
    // }
}