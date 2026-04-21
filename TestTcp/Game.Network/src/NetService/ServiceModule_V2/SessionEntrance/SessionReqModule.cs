
using System.ComponentModel;

namespace Game.Network.Service
{
    public class SessionReqModule : IServiceModule
                                    , IRequest<SessionReq, SessionRsp>
    {        
        private INetAPI _net;
        private ISelfWriter _self;
        private IGameWriter _game;
        private IHostReader _host;

        private bool _onRequest;

        public void Init(ServiceContext_V2 context)
        {
            _net = context.Net;
            _self = context.Self;
            _game = context.Games;
            _host = context.Host;
            _onRequest = false;
        }

        public void RequestEnter(Action<SessionRsp> succ, Action<string> fail)
        {
            var req = new SessionReq(SessionReqType.ReqEnter, _self.sessionInfo.id);
            Request(req, succ, fail);
        }

        public void RequestExit(Action<SessionRsp> succ, Action<string> fail)
        {
            var req = new SessionReq(SessionReqType.ReqExit, _self.sessionInfo.id, _self.sessionInfo.playerId);
            Request(req, succ, fail);
        }

        public void Request(SessionReq msg, Action<SessionRsp> succ, Action<string> fail)
        {
            var payload = new byte[SessionReq.Codec.GetSize(msg)];
            PacketWriter writer = new(payload);
            SessionReq.Codec.Write(ref writer, msg); 

            switch (msg.type)
            {
                case SessionReqType.ReqEnter:
                    _  = _net.AsyncRequestQuery(NetEventHandlerId.Constant.Session, _host.connId, payload, 10000, 
                        (connId, result) => ReqEnterCallBack(connId, result, succ, fail));
                    return;
                case SessionReqType.ReqExit:
                    _  = _net.AsyncRequestQuery(NetEventHandlerId.Constant.Session, _host.connId, payload, 10000, 
                        (connId, result) => ReqExitCallBack(connId, result, succ, fail));
                    return;
                default:
                    return;
            }   
        }

        private void ReqEnterCallBack(ConnId connId, QueryTaskResult result, Action<SessionRsp> succ, Action<string> fail)
        {
            if (!_onRequest) throw new InvalidOperationException();
            
            if (connId != _host.connId) fail.Invoke("Rsp is differnt with host"); 
            else if (result.IsTimeOut) fail.Invoke("Time Out");
            else if (result.IsResponded)
            {
                try
                {
                    PacketReader reader = new(result.AnswerRaw);
                    SessionRsp rsp = SessionRsp.Codec.Read(ref reader);
                    if (rsp.type == SessionRspType.Accepted &&
                        (_game.IsSessionActive(rsp.sessionId) || _game.TryCreateSession(rsp.sessionId))
                        && _game.TryEnterPlayer(rsp.sessionId, rsp.playerId))
                    {
                        _self.sessionWriter.Enter(rsp.playerId);
                        succ.Invoke(rsp);
                    }
                }
                catch (Exception e)
                {
                    fail.Invoke($"Fail during Reading Rsp. Exception : {e.Message}");
                }
            }
            _onRequest = false;
            return;
        }

        private void ReqExitCallBack(ConnId connId, QueryTaskResult result, Action<SessionRsp> succ, Action<string> fail)
        {
            if (connId != _host.connId)
            {
                fail.Invoke("Rsp is differnt with host"); 
                return;
            }

            if (result.IsResponded)
            {
                
            }

        }


    }
}