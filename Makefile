# #  LittleSDK Bootstrapping
SDK_PATH=deps/sdk
include $(if $(SDK_PATH),$(shell test ! -e "$(SDK_PATH)/setup.mk" && git clone git@github.com:littletoolkit/littlesdk.git "$(SDK_PATH)";echo "$(SDK_PATH)/setup.mk"))
# EOF -- vim: ft=make
