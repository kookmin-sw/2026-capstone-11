using System;
using UnityEngine;
using Animations;
using System.Collections.Generic;
using System.Collections;
using events.client;
using UnityEngine.UIElements;

namespace events.Animation
{
    public class AnimationEventBus : MonoBehaviour, IEventBus
    {
        private static AnimationEventBus _instance;
        public static AnimationEventBus Instance;

        private Dictionary<RenderCommandType, IAnimationDispatchHandler> dispatchHandlers = new Dictionary<RenderCommandType, IAnimationDispatchHandler>
        {
            { RenderCommandType.Move, new MoveDispatch() },
            { RenderCommandType.Deploy, new SpawnDispatch() },
            { RenderCommandType.Withdraw, new DestroyDispatch() },
            { RenderCommandType.Damage, new DamageDispatch() },
            { RenderCommandType.DrawCard, new DrawCardDispatch() },
            { RenderCommandType.UseCard, new UseCardDispatch() },
            { RenderCommandType.Event, new EventDispatch() }
        };

        private Queue<RuntimeRenderCommand> queue = new();
        private bool isPlay;

        // 싱글톤 초기화 구현
        void Awake()
        {
            if (!_instance)
            {
                _instance = this;
                Instance = _instance;
            }
            else
            {
                Destroy(gameObject);
            }
        }

        // 이벤트 구독자 목록
        private Dictionary<Type, List<Action<IBaseEvent>>> subscribers = new Dictionary<Type, List<Action<IBaseEvent>>>();

        public void Publish<T>(T eventData) where T : IBaseEvent
        {
            Type eventType = typeof(T);

            if (subscribers.ContainsKey(eventType))
            {
                foreach (var callback in subscribers[eventType])
                {
                    callback(eventData);
                }
            }
        }

        public void Subscribe<T>(Action<T> callback) where T : IBaseEvent
        {
            Type eventType = typeof(T);

            if (!subscribers.ContainsKey(eventType))
            {
                subscribers[eventType] = new List<Action<IBaseEvent>>();
            }

            subscribers[eventType].Add((e) => callback((T)e));
        }

        public void Unsubscribe<T>(Action<T> callback) where T : IBaseEvent
        {
            Type eventType = typeof(T);

            if (subscribers.ContainsKey(eventType))
            {
                subscribers[eventType].Remove((e) => callback((T)e));
            }
        }

        public void Enqueue(RuntimeRenderCommand command)
        {
            queue.Enqueue(command);
            
            if (!isPlay)
            {
                isPlay = true;
                Publish(new IClientEvents.LockInputEvent(isPlay));

                StartCoroutine(ProcessQueue());
            }
        }

        public void Enqueue(IEnumerable<RuntimeRenderCommand> commands)
        {
            foreach (var command in commands)
            {
                Debug.Log($"Enqueuing {command.type}");
                queue.Enqueue(command);
            }

            if (!isPlay)
            {
                isPlay = true;
                Publish(new IClientEvents.LockInputEvent(isPlay));
                StartCoroutine(ProcessQueue());
            }
        }

        private IEnumerator ProcessQueue()
        {
            while (queue.Count > 0)
            {
                var command = queue.Dequeue();

                Dispatch(command);

                yield return new WaitForSeconds(command.duration);
            }

            isPlay = false;
            Publish(new IClientEvents.LockInputEvent(isPlay));
        }

        private void Dispatch(RuntimeRenderCommand cmd)
        {
            if (dispatchHandlers.ContainsKey(cmd.type))
            {
                Debug.Log($"Executing {cmd.type}");
                dispatchHandlers[cmd.type].Dispatch(cmd, this);
            }
        }
    }
}