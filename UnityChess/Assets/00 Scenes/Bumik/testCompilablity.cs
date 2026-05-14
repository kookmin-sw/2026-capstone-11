using UnityEngine;
using Game.Network;
using System;

public class testCompilablity
{

}

public interface IPacketMeta<T>
{
    static uint PacketId { get; }
    static IPacketCodec<T> Codec { get; }
}

public interface CIRequest<TMessage, TResult>
    where TMessage : IPacketMeta<TMessage>
    where TResult : IPacketMeta<TResult>
{
    void Request(TMessage msg, Action<TResult> succ, Action<string> fail);
}

public interface CIRequestHandler<TMessage, TResult>
    where TMessage : IPacketMeta<TMessage>
    where TResult : IPacketMeta<TResult>
{
    TResult Handle(ConnId connId, TMessage msg);
}