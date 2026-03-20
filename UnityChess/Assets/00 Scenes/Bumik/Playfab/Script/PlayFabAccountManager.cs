using UnityEngine;
using System;
using System.Collections.Generic;
using PlayFab;
using PlayFab.ClientModels;
using System.ComponentModel;
using Unity.VisualScripting;

public class PlayFabAccountManager : MonoBehaviour
{
    public static PlayFabAccountManager Instance { get; private set; }

    public bool IsLoggedIn { get; private set; }
    public string PlayFabId { get; private set; }
    public string InGameDisplayName {get; private set;}
    public string SessionTicket { get; private set; }

    private void Awake()
    {
        if (Instance == null) Instance = this;
        else
        {
            Destroy(gameObject);
            return;
        }
    }

    public void Register(
        string username,
        string displayName,
        string email,
        string password,
        Action onSuccess = null,
        Action<string> onFail = null)
    {
        var request = new RegisterPlayFabUserRequest
        {
            Username = username,
            DisplayName = displayName,
            Email = email,
            Password = password,
            RequireBothUsernameAndEmail = true
        };

        PlayFabClientAPI.RegisterPlayFabUser(
            request,
            result =>
            {
                IsLoggedIn = true;
                PlayFabId = result.PlayFabId;
                SessionTicket = result.SessionTicket;
                InGameDisplayName = displayName;

                Debug.Log($"[PlayFab] Register success: {PlayFabId}");
                onSuccess?.Invoke();
            },
            error =>
            {
                IsLoggedIn = false;
                Debug.Log("[PlayFab] Register failed: " + error.GenerateErrorReport());
                onFail?.Invoke(error.ErrorMessage);
            });
    }

    public void Login(
        string email,
        string password,
        Action onSuccess = null,
        Action<string> onFail = null)
    {
        var reqParams = new GetPlayerCombinedInfoRequestParams
        {
            GetPlayerProfile = true
        };
        var request = new LoginWithEmailAddressRequest
        {
            Email = email,
            Password = password,
            InfoRequestParameters = reqParams
        };

        PlayFabClientAPI.LoginWithEmailAddress(
            request,
            result =>
            {
                IsLoggedIn = true;
                PlayFabId = result.PlayFabId;
                SessionTicket = result.SessionTicket;
                InGameDisplayName = result.InfoResultPayload.PlayerProfile.DisplayName;

                Debug.Log($"[PlayFab] Login success: {PlayFabId}");
                onSuccess?.Invoke();
            },
            error =>
            {
                IsLoggedIn = false;
                Debug.Log("[PlayFab] Login failed: " + error.GenerateErrorReport());
                onFail?.Invoke(error.ErrorMessage);
            });
    }

    public void ClearSession()
    {
        IsLoggedIn = false;
        PlayFabId = null;
        SessionTicket = null;
        InGameDisplayName = null;
    }
}
