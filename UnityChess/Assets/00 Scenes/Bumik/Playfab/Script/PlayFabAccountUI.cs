using UnityEngine;
using TMPro;
using System.Linq;
using UnityEngine.UI;
using System.Collections.Generic;
using PlayFab;
using UnityEngine.SceneManagement;
using DG.Tweening;
using Title.UI;

public class PlayFabAccountUI : MonoBehaviour
{

    [SerializeField] private TitleInputController controller;

    [Header("Panel")]
    [SerializeField] private GameObject registerPanel;
    [SerializeField] private GameObject loginPanel;
    

    [Header("Register")]
    [SerializeField] private TMP_InputField registerUsernameInput;
    [SerializeField] private TMP_InputField registerDisplaynameInput;
    [SerializeField] private TMP_InputField registerEmailInput;
    [SerializeField] private TMP_InputField registerPasswordInput;
    [SerializeField] private TMP_InputField registerPasswordCheck;

    [Header("Login")]
    [SerializeField] private TMP_InputField loginEmailInput;
    [SerializeField] private TMP_InputField loginPasswordInput;

    [Header("Button")]
    [SerializeField] private Button loginButton;
    [SerializeField] private Button logoutButton;
    [SerializeField] private Button registerButton;
    [SerializeField] private List<Button> closePanelButton;

    [Header("Info Field")]
    [SerializeField] private TMP_Text InfoField;
    [SerializeField] private TMP_Text NameField;

    [Header("API Call Guard Button")]
    [SerializeField] private List<Button> ButtonToGuard;

    [Header("Hard Logout toggle (for test)")]
    [SerializeField] private bool hardLogout = false;

    private bool APICallGuardFlag = false;
    private Tween infoTween;

    private void Start()
    {
        InfoField.text = "";
        NameField.text = "";

        loginButton.onClick.AddListener(() => controller.SetState(TitleState.LoginPanelOpened));
        logoutButton.onClick.AddListener(() => controller.SetState(TitleState.WaitingForInput));
        registerButton.onClick.AddListener(() => controller.SetState(TitleState.RegisterPanelOpened));

        foreach (var btn in closePanelButton)
        {
            btn.onClick.AddListener(() => controller.SetState(TitleState.WaitingForInput));
        }
    }

    private void SwitchButton()
    {
        bool isLoggedin = PlayFabAccountManager.Instance.IsLoggedIn;

        loginButton.gameObject.SetActive(!isLoggedin);
        logoutButton.gameObject.SetActive(isLoggedin);
        registerButton.gameObject.SetActive(!isLoggedin);
    }

    private void ClearLoginInputField()
    {
        loginEmailInput.text = string.Empty;
        loginPasswordInput.text = string.Empty;
    }

    private void ClearRegisterInputField()
    {
        registerUsernameInput.text = string.Empty;
        registerDisplaynameInput.text = string.Empty;
        registerEmailInput.text = string.Empty;
        registerPasswordInput.text = string.Empty;
        registerPasswordCheck.text = string.Empty;
    }

    public void GuardButton()
    {
        APICallGuardFlag = true;
        foreach (var bt in ButtonToGuard) 
            bt.interactable = false;
    }

    public void ReleaseButton()
    {
        APICallGuardFlag = false;
        foreach (var bt in ButtonToGuard) 
            bt.interactable = true;
    }

    public void UpdateInfoField()
    {
        infoTween?.Kill();

        bool isLoggedIn = PlayFabAccountManager.Instance.IsLoggedIn; 
        InfoField.text = isLoggedIn ? "로그인 성공!" : "로그인 실패!";

        if (isLoggedIn) 
            NameField.text = "환영합니다, " + PlayFabAccountManager.Instance.InGameDisplayName + "님";
        
        infoTween = InfoField.DOColor(Color.clear, 5f);
    }

    public void OnClickRegister()
    {
        if (APICallGuardFlag) return;

        string username = registerUsernameInput.text.Trim();
        string displayName = registerDisplaynameInput.text.Trim();
        string email = registerEmailInput.text.Trim();
        string password = registerPasswordInput.text;
        string passwordCheck = registerPasswordCheck.text;

        if (string.IsNullOrWhiteSpace(username) ||
            string.IsNullOrWhiteSpace(email) ||
            string.IsNullOrWhiteSpace(displayName) ||
            string.IsNullOrWhiteSpace(password) ||
            string.IsNullOrWhiteSpace(passwordCheck))
        {
            Debug.Log("회원가입 입력값이 비어 있습니다.");
            return;
        }
        
        if ( displayName.Count() < 3 || displayName.Count() > 25)
        {
            Debug.Log("DisplayName 길이 오류. 3 ~ 25자의 이름 사용");
            return;
        }

        if (!string.Equals(password, passwordCheck))
        {
            Debug.Log("2차 비밀번호 오류");
            return;
        }

        GuardButton();
        PlayFabAccountManager.Instance.Register(
            username,
            displayName,
            email,
            password,
            onSuccess: () =>
            {
                Debug.Log("회원가입 성공");
                UpdateInfoField();
                ReleaseButton();
                SwitchButton();
                ClearRegisterInputField();
                registerPanel.SetActive(false);
            },
            onFail: error =>
            {
                Debug.Log("회원가입 실패: " + error);
                UpdateInfoField();
                ReleaseButton();
                SwitchButton();
            });
    }

    public void OnClickLogin()
    {
        if (APICallGuardFlag) return;

        string email = loginEmailInput.text.Trim();
        string password = loginPasswordInput.text;

        if (string.IsNullOrWhiteSpace(email) || string.IsNullOrWhiteSpace(password))
        {
            Debug.Log("로그인 입력값이 비어 있습니다.");
            return;
        }

        GuardButton();
        PlayFabAccountManager.Instance.Login(
            email,
            password,
            onSuccess: () =>
            {
                Debug.Log("로그인 성공");
                UpdateInfoField();
                ReleaseButton();
                SwitchButton();
                ClearLoginInputField();
                loginPanel.SetActive(false);
            },
            onFail: error =>
            {
                Debug.Log("로그인 실패: " + error);
                UpdateInfoField();
                ReleaseButton();
                SwitchButton();
            });
    }

    public void OnCkickLogout()
    {
        if (APICallGuardFlag) return;

        GuardButton();
        PlayFabAccountManager.Instance.Logout(hardLogout);

        ReleaseButton();
        SwitchButton();

        NameField.text = "";
    }
}
