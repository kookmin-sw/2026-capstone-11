using UnityEngine;
using System;
using PlayFab;
using PlayFab.ClientModels;

public class PlayFabAccountManager : MonoBehaviour
{
    public static PlayFabAccountManager Instance { get; private set; }

    public bool IsLoggedIn { get; private set; }
    public string PlayFabId { get; private set; }
    public string InGameDisplayName { get; private set; }
    public string SessionTicket { get; private set; }


    public string EntityId { get; private set; }
    public string EntityType { get; private set; }
    public string EntityToken { get; private set; }

    private void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
            DontDestroyOnLoad(gameObject);
        }
        else
        {
            Destroy(gameObject);
            return;
        }
    }

    public void AutoLogin(
        Action onSuccess = null,
        Action<string> onFail = null)
    {
        if (!PlayerPrefs.HasKey("CustomID"))
        {
            Debug.Log("[Playfab] Auto Login failed: No Custom ID");
            onFail?.Invoke("No Custom ID");
            
            return;
        }

        string customId = PlayerPrefs.GetString("CustomID");

        var request = new LoginWithCustomIDRequest
        {
            CustomId = customId,
            CreateAccount = false,
            InfoRequestParameters = new GetPlayerCombinedInfoRequestParams
            {
                GetPlayerProfile = true
            }
        };

        PlayFabClientAPI.LoginWithCustomID(
            request,
            result =>
            {
                IsLoggedIn = true;
                PlayFabId = result.PlayFabId;
                SessionTicket = result.SessionTicket;
                InGameDisplayName = result.InfoResultPayload.PlayerProfile.DisplayName;

                EntityId = result.EntityToken.Entity.Id;
                EntityType = result.EntityToken.Entity.Type;
                EntityToken = result.EntityToken.EntityToken;

                Debug.Log($"[PlayFab] Auto Login success: {PlayFabId}");
                onSuccess?.Invoke();
            },
            error =>
            {
                IsLoggedIn = false;
                Debug.Log("[PlayFab] Auto Login failed: " + error.GenerateErrorReport());
                onFail?.Invoke(error.ErrorMessage);
            });
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

                EntityId = result.EntityToken.Entity.Id;
                EntityType = result.EntityToken.Entity.Type;
                EntityToken = result.EntityToken.EntityToken;

                LinkDeviceCustomId();

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

                EntityId = result.EntityToken.Entity.Id;
                EntityType = result.EntityToken.Entity.Type;
                EntityToken = result.EntityToken.EntityToken;

                LinkDeviceCustomId();

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

    private void LinkDeviceCustomId()
    {
        if (!PlayerPrefs.HasKey("CustomID"))
        {
            PlayerPrefs.SetString("CustomID", Guid.NewGuid().ToString());
            PlayerPrefs.Save();
        }

        string customId = PlayerPrefs.GetString("CustomID");

        var request = new LinkCustomIDRequest
        {
            CustomId = customId,
            ForceLink = false
        };

        PlayFabClientAPI.LinkCustomID(
            request,
            result =>
            {
                Debug.Log($"[Playfab] CustomID Link success: {customId}");
            },
            error =>
            {
                Debug.Log("[Playfab] CustomID Link falied: " + error.GenerateErrorReport());
            });
    }

    public void Logout(bool clearAutoLogin = false)
    {
        ClearSession();

        if (clearAutoLogin)
        {
            PlayerPrefs.DeleteKey("CustomID");
            PlayerPrefs.Save();
        }
    }

    public void ClearSession()
    {
        IsLoggedIn = false;
        PlayFabId = null;
        SessionTicket = null;
        InGameDisplayName = null;
    }
}
