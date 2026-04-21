

using System.Runtime.CompilerServices;
using Game.Network;
using Game.Network.Protocol;
using Game.Network.Service;

public class EnterResponseModule : IServiceModule, INetReceiveEventHandler
                                , IRequestHandler<PeerEntranceRequest, PeerEntranceResponse>
{
    public int HandlerId => NetEventHandlerId.Constant.PeerEntrance;
    private INetAPI _net;
    private IPeerDictWriter _other;
    private IServiceEventPublisher _eventPublisher;
    private ISelfWriter _self;

    public void Init(ServiceContext_V2 context)
    {
        _net = context.Net;
        _eventPublisher = context.EventBridge;
        _other = context.Other;
        _self = context.Self;

        context.Net.SetReceiveHandler(this);
    }

    public PeerEntranceResponse Handle(ConnId connId, PeerEntranceRequest request)
    {
        // TODO: PeerInfo 검증
        var newPeer = new Peer(connId, request.Info);
        _other.AddPeer(connId, newPeer);
        _eventPublisher.PublishEnterEvents(newPeer);

        return new PeerEntranceResponse(true, _self.connWriter.instance);
    }

    public void OnQuery(ConnId connId, int queryNum, byte[] raw)
    {
        try
        {
            PacketReader reader = new PacketReader(raw);
            PeerEntranceRequest request = PeerEntranceRequest.Codec.Read(ref reader);

            var response = Handle(connId, request);
            var payload = new byte[PeerEntranceResponse.Codec.GetSize(response)];
            var writer  = new PacketWriter(payload);
            PeerEntranceResponse.Codec.Write(ref writer, response);

            _net.Send(NetEventHandlerId.Constant.PeerEntrance, queryNum, connId, payload);
            
        } 
        catch (Exception e)
        {
            Log.WriteLog($"Peer Enter Req Fail: {e.Message}");
            _other.RemovePeer(connId);
        }
    }

}