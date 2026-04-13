using System;
using System.Text;
using System.Threading.Tasks;
using Game.Network;
using Game.Network.Protocol;
using PlayFab.EconomyModels;
using TMPro;
using Unity.VisualScripting;
using UnityEngine;

public class NetworkTestSceneMain : MonoBehaviour
{
    [SerializeField] private NetworkManagerUnity manager;
    [SerializeField] private QueryPopUp queryPopUp;
    [SerializeField] private TMP_Text gameStatus;
    [SerializeField] private UnitCharManager charManager;

    void Start()
    {
        manager.Init();
        queryPopUp.Init();
        charManager.InitGrid();

        manager.Session.SetName(GameInitializer.Instance.Data.PlayerName);
        manager.Session.Events.OnGetQuery = queryPopUp.PopScreen;
        manager.Session.Events.OnConnectHello = () => {Debug.Log("OnHello!");};
        manager.Session.Events.OnDisconnectUnsafe = () => {Debug.Log("DisconnectUnsafe!");};
        manager.Session.Events.OnMessageReceive = (raw) => {charManager.RenderBoard(Encoding.UTF8.GetString(raw));};




        manager.Session.StartSession(GameInitializer.Instance.Data.IpAddr, GameInitializer.Instance.Data.PortNum);
    }

    void Update() {}



}
